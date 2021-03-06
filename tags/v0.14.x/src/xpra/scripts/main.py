# This file is part of Xpra.
# Copyright (C) 2011 Serviware (Arthur Huillet, <ahuillet@serviware.com>)
# Copyright (C) 2010-2014 Antoine Martin <antoine@devloop.org.uk>
# Copyright (C) 2008 Nathaniel Smith <njs@pobox.com>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import sys
import os
import stat
import socket
import time
import optparse
import logging
from subprocess import Popen, PIPE
import signal
import shlex
import traceback

from xpra import __version__ as XPRA_VERSION
from xpra.dotxpra import DotXpra, osexpand
from xpra.platform.features import LOCAL_SERVERS_SUPPORTED, SHADOW_SUPPORTED, CAN_DAEMONIZE
from xpra.platform.options import add_client_options
from xpra.platform.paths import get_default_socket_dir
from xpra.net.bytestreams import TwoFileConnection, SocketConnection
from xpra.net.protocol import ConnectionClosedException
from xpra.scripts.config import OPTION_TYPES, ENCRYPTION_CIPHERS, \
    make_defaults_struct, parse_bool, print_bool, validate_config, has_sound_support


SOCKET_TIMEOUT = int(os.environ.get("XPRA_SOCKET_TIMEOUT", 10))
TCP_NODELAY = int(os.environ.get("XPRA_TCP_NODELAY", "1"))


def enabled_str(v):
    if v:
        return "enabled"
    else:
        return "disabled"


def warn(msg):
    #use this function to print warnings
    #we must write to stderr to prevent
    #the output from interfering when running as proxy over ssh
    #(which uses stdin / stdout as communication channel)
    sys.stderr.write(msg+"\n")

def nox():
    if "DISPLAY" in os.environ:
        del os.environ["DISPLAY"]
    # This is an error on Fedora/RH, so make it an error everywhere so it will
    # be noticed:
    import warnings
    warnings.filterwarnings("error", "could not open display")


supports_shadow = SHADOW_SUPPORTED
supports_server = LOCAL_SERVERS_SUPPORTED
if supports_server:
    try:
        from xpra.x11.bindings.wait_for_x_server import wait_for_x_server    #@UnresolvedImport @UnusedImport
    except:
        supports_server = False


class InitException(Exception):
    pass
class InitInfo(Exception):
    pass
class InitExit(Exception):
    def __init__(self, status, msg):
        self.status = status
        Exception.__init__(self, msg)

#this parse doesn't exit when it encounters an error,
#allowing us to deal with it better and show a UI message if needed.
class ModifiedOptionParser(optparse.OptionParser):
    def error(self, msg):
        raise InitException(msg)
    def exit(self, status=0, msg=None):
        raise InitExit(status, msg)


def fixup_defaults(defaults):
    for k in ("debug", "encoding", "microphone-codec", "speaker-codec"):
        fn = k.replace("-", "_")
        v = getattr(defaults, fn)
        if "help" in v:
            if os.environ.get("XPRA_SKIP_UI", "0")=="0":
                #skip-ui: we're running in subprocess, don't bother spamming stderr
                sys.stderr.write(("Warning: invalid 'help' option found in '%s' configuration\n" % k) +
                             " this should only be used as a command line argument\n")
            if k in ("encoding", "debug", "sound-source"):
                setattr(defaults, fn, "")
            else:
                v.remove("help")


def main(script_file, cmdline):
    from xpra.platform import init as platform_init, clean as platform_clean, command_error, command_info, get_main_fallback
    if len(cmdline)==1:
        fm = get_main_fallback()
        if fm:
            return fm()

    try:
        platform_init("Xpra")
        try:
            defaults = make_defaults_struct()
            fixup_defaults(defaults)
            options, args = do_parse_cmdline(cmdline, defaults)
            if not args:
                print("xpra: need a mode")
                return -1
            mode = args.pop(0)
            def err(*args):
                raise InitException(*args)
            return run_mode(script_file, err, options, args, mode, defaults)
        except SystemExit:
            raise
        except InitExit:
            e = sys.exc_info()[1]
            if str(e) and e.args and (e.args[0] or len(e.args)>1):
                command_info("%s" % e)
            return e.status
        except InitInfo:
            command_info("%s" % sys.exc_info()[1])
            return 0
        except InitException:
            e = sys.exc_info()[1]
            command_error("xpra initialization error: %s" % e)
            return 1
        except Exception:
            command_error("xpra main error:\n%s" % traceback.format_exc())
            return 1
    finally:
        platform_clean()


def fixup_debug_option(value):
    """ backwards compatible parsing of the debug option, which used to be a boolean """
    if not value:
        return ""
    value = str(value)
    if value.strip().lower() in ("yes", "true", "on", "1"):
        return "all"
    if value.strip().lower() in ("no", "false", "off", "0"):
        return ""
    #if we're here, the value should be a CSV list of categories
    return value

def _csvstr(value):
    if type(value) in (tuple, list):
        return ",".join(str(x).lower().strip() for x in value)
    elif type(value)==str:
        return value.strip().lower()
    raise Exception("don't know how to convert %s to a csv list!" % type(value))

def _nodupes(s):
    from xpra.util import remove_dupes
    return remove_dupes(x.strip().lower() for x in s.split(","))

def fixup_video_all_or_none(options):
    from xpra.codecs.video_helper import ALL_VIDEO_ENCODER_OPTIONS as aveco
    from xpra.codecs.video_helper import ALL_CSC_MODULE_OPTIONS as acsco
    from xpra.codecs.video_helper import ALL_VIDEO_DECODER_OPTIONS as avedo
    vestr   = _csvstr(options.video_encoders)
    cscstr  = _csvstr(options.csc_modules)
    vdstr   = _csvstr(options.video_decoders)
    def getlist(strarg, help_txt, all_list):
        if strarg=="help":
            raise InitInfo("the following %s may be available: %s" % (help_txt, ", ".join(all_list)))
        elif strarg=="none":
            return []
        elif strarg=="all":
            return all_list
        else:
            return _nodupes(strarg)
    options.video_encoders  = getlist(vestr,    "video encoders",   aveco)
    options.csc_modules     = getlist(cscstr,   "csc modules",      acsco)
    options.video_decoders  = getlist(vdstr,    "video decoders",   avedo)

def fixup_encodings(options):
    from xpra.codecs.loader import ALL_OLD_ENCODING_NAMES_TO_NEW, PREFERED_ENCODING_ORDER
    if options.encoding:
        #fix old encoding names if needed:
        options.encoding = ALL_OLD_ENCODING_NAMES_TO_NEW.get(options.encoding, options.encoding)
    estr = _csvstr(options.encodings)
    if estr=="all":
        #replace with an actual list
        options.encodings = PREFERED_ENCODING_ORDER
        return
    encodings = _nodupes(estr)
    if "rgb" in encodings:
        if "rgb24" not in encodings:
            encodings.append("rgb24")
        if "rgb32" not in encodings:
            encodings.append("rgb32")
    options.encodings = encodings

def fixup_compression(options):
    #packet compression:
    from xpra.net import compression
    cstr = _csvstr(options.compressors)
    if cstr=="none":
        compressors = []
    elif cstr=="all":
        compressors = compression.get_enabled_compressors()
    else:
        compressors = _nodupes(cstr)
        unknown = [x for x in compressors if x and x not in compression.ALL_COMPRESSORS]
        if unknown:
            warn("warning: invalid compressor(s) specified: %s" % (", ".join(unknown)))
    for c in compression.ALL_COMPRESSORS:
        enabled = c in compression.get_enabled_compressors() and c in compressors
        setattr(compression, "use_%s" % c, enabled)
    if not compression.get_enabled_compressors():
        #force compression level to zero since we have no compressors available:
        options.compression_level = 0

def fixup_packetencoding(options):
    #packet encoding
    from xpra.net import packet_encoding
    pestr = _csvstr(options.packet_encoders)
    if pestr=="all":
        packet_encoders = packet_encoding.get_enabled_encoders()
    else:
        packet_encoders = _nodupes(pestr)
        unknown = [x for x in packet_encoders if x and x not in packet_encoding.ALL_ENCODERS]
        if unknown:
            warn("warning: invalid packet encoder(s) specified: %s" % (", ".join(unknown)))
    for pe in packet_encoding.ALL_ENCODERS:
        enabled = pe in packet_encoding.get_enabled_encoders() and pe in packet_encoders
        setattr(packet_encoding, "use_%s" % pe, enabled)
    #verify that at least one encoder is available:
    if not packet_encoding.get_enabled_encoders():
        raise InitException("at least one valid packet encoder must be enabled (not '%s')" % options.packet_encoders)


def parse_cmdline(cmdline):
    defaults = make_defaults_struct()
    return do_parse_cmdline(cmdline, defaults)

def do_parse_cmdline(cmdline, defaults):
    #################################################################
    ## NOTE NOTE NOTE
    ##
    ## If you modify anything here, then remember to update the man page
    ## (xpra.1) as well!
    ##
    ## NOTE NOTE NOTE
    #################################################################
    command_options = [
                        "\t%prog attach [DISPLAY]\n",
                        "\t%prog detach [DISPLAY]\n",
                        "\t%prog screenshot filename [DISPLAY]\n",
                        "\t%prog info [DISPLAY]\n",
                        "\t%prog control DISPLAY command [arg1] [arg2]..\n",
                        "\t%prog version [DISPLAY]\n"
                      ]
    server_modes = []
    if supports_server:
        server_modes.append("start")
        server_modes.append("upgrade")
        #display: default to required
        dstr = " DISPLAY"
        if defaults.displayfd:
            #display argument is optional (we can use "-displayfd")
            dstr = " [DISPLAY]"
        command_options = ["\t%prog start"+dstr+"\n",
                           "\t%prog stop [DISPLAY]\n",
                           "\t%prog exit [DISPLAY]\n",
                           "\t%prog list\n",
                           "\t%prog upgrade [DISPLAY]\n",
                           ] + command_options
    if supports_shadow:
        server_modes.append("shadow")
        command_options.append("\t%prog shadow [DISPLAY]\n")
    if not supports_server:
        command_options.append("(This xpra installation does not support starting local servers.)")

    parser = ModifiedOptionParser(version="xpra v%s" % XPRA_VERSION,
                          usage="\n" + "".join(command_options))
    hidden_options = {"display" : defaults.display,
                      "displayfd" : defaults.displayfd,
                      "wm_name" : defaults.wm_name}
    group = optparse.OptionGroup(parser, "Server Options",
                "These options are only relevant on the server when using the %s mode." %
                " or ".join(["'%s'" % x for x in server_modes]))
    parser.add_option_group(group)
    #we support remote start, so we need those even if we don't have server support:
    group.add_option("--start-child", action="append",
                      dest="start_child", metavar="CMD", default=list(defaults.start_child or []),
                      help="program to spawn in new server (may be repeated) (default: %default)")
    group.add_option("--exit-with-children", action="store_true",
                      dest="exit_with_children", default=defaults.exit_with_children,
                      help="Terminate server when --start-child command(s) exit")
    if supports_server:
        group.add_option("--tcp-proxy", action="store",
                          dest="tcp_proxy", default=defaults.tcp_proxy,
                          metavar="HOST:PORT",
                          help="The address to which non-xpra packets will be forwarded.")
    else:
        hidden_options["tcp_proxy"] = ""
    if (supports_server or supports_shadow) and CAN_DAEMONIZE:
        group.add_option("--no-daemon", action="store_false",
                          dest="daemon", default=True,
                          help="Don't daemonize when running as a server")
        group.add_option("--log-file", action="store",
                      dest="log_file", default=defaults.log_file,
                      help="When daemonizing, this is where the log messages will go (default: %default)."
                      + " If a relative filename is specified the it is relative to --socket-dir,"
                      + " the value of '$DISPLAY' will be substituted with the actual display used"
                      )
    else:
        hidden_options["daemon"] = False
        hidden_options["log_file"] = defaults.log_file

    if (supports_server or supports_shadow):
        group.add_option("--exit-with-client", action="store_true",
                          dest="exit_with_client", default=False,
                          help="Terminate the server when the last client disconnects")
    else:
        hidden_options["exit_with_client"] = False
    if supports_server:
        group.add_option("--use-display", action="store_true",
                          dest="use_display", default=defaults.use_display,
                          help="Use an existing display rather than starting one with xvfb")
        group.add_option("--xvfb", action="store",
                          dest="xvfb",
                          default=defaults.xvfb,
                          metavar="CMD",
                          help="How to run the headless X server (default: '%default')")
        group.add_option("--fake-xinerama", action="store_true",
                          dest="fake_xinerama",
                          default=defaults.fake_xinerama,
                          help="Enable fake xinerama support (default: %s)" % enabled_str(defaults.fake_xinerama))
        group.add_option("--no-fake-xinerama", action="store_false",
                          dest="fake_xinerama",
                          default=defaults.fake_xinerama,
                          help="Disable fake xinerama support (default: %s)" % enabled_str(defaults.fake_xinerama))
    else:
        hidden_options["use_display"] = False
        hidden_options["xvfb"] = ''
        hidden_options["fake_xinerama"] = False
    if supports_server or supports_shadow:
        group.add_option("--bind-tcp", action="append",
                          dest="bind_tcp", default=list(defaults.bind_tcp or []),
                          metavar="[HOST]:PORT",
                          help="Listen for connections over TCP (use --password-file to secure it)."
                            + " You may specify this option multiple times with different host and port combinations")
    else:
        hidden_options["bind_tcp"] = []
    if (supports_server or supports_shadow):
        group.add_option("--mdns", action="store_true",
                          dest="mdns", default=defaults.mdns,
                          help="Enable publishing of session information via mDNS (default: %s)" % enabled_str(defaults.mdns))
        group.add_option("--no-mdns", action="store_false",
                          dest="mdns", default=defaults.mdns,
                          help="Disable publishing of session information via mDNS (default: %s)" % enabled_str(defaults.mdns))
    else:
        hidden_options["mdns"] = False
    if supports_server:
        group.add_option("--pulseaudio", action="store_true",
                      dest="pulseaudio", default=defaults.pulseaudio,
                      help="Enable starting of a pulseaudio server for the session")
        group.add_option("--no-pulseaudio", action="store_false",
                      dest="pulseaudio", default=defaults.pulseaudio,
                      help="Disable starting of a pulseaudio server for the session")
        group.add_option("--pulseaudio-command", action="store",
                      dest="pulseaudio_command", default=defaults.pulseaudio_command,
                      help="The command used to start the pulseaudio server (default: '%default')")
        group.add_option("--dbus-proxy", action="store_true",
                      dest="dbus_proxy", default=defaults.dbus_proxy,
                      help="Enable forwarding of dbus calls from the client (default: %s)" % enabled_str(defaults.dbus_proxy))
        group.add_option("--no-dbus-proxy", action="store_false",
                      dest="dbus_proxy", default=defaults.dbus_proxy,
                      help="Disable forwarding of dbus calls from the client (default: %s)" % enabled_str(defaults.dbus_proxy))
    else:
        hidden_options["pulseaudio"] = False
        hidden_options["pulseaudio_command"] = ""
        hidden_options["dbus_proxy"] = False

    group = optparse.OptionGroup(parser, "Server Controlled Features",
                "These options can be used to turn certain features on or off, "
                "they can be specified on the client or on the server, "
                "but the client cannot enable them if they are disabled on the server.")
    parser.add_option_group(group)
    group.add_option("--clipboard", action="store_true",
                      dest="clipboard", default=defaults.clipboard,
                      help="Enable clipboard support (default: %s)" % enabled_str(defaults.clipboard))
    group.add_option("--no-clipboard", action="store_false",
                      dest="clipboard", default=defaults.clipboard,
                      help="Disable clipboard support (default: %s)" % enabled_str(defaults.clipboard))
    group.add_option("--notifications", action="store_true",
                      dest="notifications", default=defaults.notifications,
                      help="Enable forwarding of system notifications (default: %s)" % enabled_str(defaults.notifications))
    group.add_option("--no-notifications", action="store_false",
                      dest="notifications", default=defaults.notifications,
                      help="Disable forwarding of system notifications (default: %s)" % enabled_str(defaults.notifications))
    group.add_option("--system-tray", action="store_true",
                      dest="system_tray", default=defaults.system_tray,
                      help="Enable forwarding of system tray icons (default: %s)" % enabled_str(defaults.system_tray))
    group.add_option("--no-system-tray", action="store_false",
                      dest="system_tray", default=defaults.system_tray,
                      help="Disable forwarding of system tray icons (default: %s)" % enabled_str(defaults.system_tray))
    group.add_option("--cursors", action="store_true",
                      dest="cursors", default=defaults.cursors,
                      help="Enable forwarding of custom application mouse cursors (default: %s)" % enabled_str(defaults.cursors))
    group.add_option("--no-cursors", action="store_false",
                      dest="cursors", default=defaults.cursors,
                      help="Disable forwarding of custom application mouse cursors (default: %s)" % enabled_str(defaults.cursors))
    group.add_option("--bell", action="store_true",
                      dest="bell", default=defaults.bell,
                      help="Enable forwarding of the system bell (default: %s)" % enabled_str(defaults.bell))
    group.add_option("--no-bell", action="store_false",
                      dest="bell", default=defaults.bell,
                      help="Disable forwarding of the system bell (default: %s)" % enabled_str(defaults.bell))
    if os.name=="posix":
        group.add_option("--xsettings", action="store_true",
                          dest="xsettings", default=defaults.xsettings,
                          help="Enable xsettings synchronization (default: %s)" % enabled_str(defaults.xsettings))
        group.add_option("--no-xsettings", action="store_false",
                          dest="xsettings", default=defaults.xsettings,
                          help="Disable xsettings synchronization (default: %s)" % enabled_str(defaults.xsettings))
    else:
        hidden_options["xsettings"] =  False
    group.add_option("--mmap", action="store_true",
                      dest="mmap", default=defaults.mmap,
                      help="Enable memory mapped transfers for local connections (default: %s)" % enabled_str(defaults.mmap))
    group.add_option("--no-mmap", action="store_false",
                      dest="mmap", default=defaults.mmap,
                      help="Disable memory mapped transfers for local connections (default: %s)" % enabled_str(defaults.mmap))
    group.add_option("--readwrite", action="store_false",
                      dest="readonly", default=defaults.readonly,
                      help="Enable keyboard input and mouse events from the clients")
    group.add_option("--readonly", action="store_true",
                      dest="readonly", default=defaults.readonly,
                      help="Disable keyboard input and mouse events from the clients")
    group.add_option("--sharing", action="store_true",
                      dest="sharing", default=defaults.sharing,
                      help="Allow more than one client to connect to the same session (default: %s)" % enabled_str(defaults.sharing))
    group.add_option("--no-sharing", action="store_false",
                      dest="sharing", default=defaults.sharing,
                      help="Do not allow more than one client to connect to the same session (default: %s)" % enabled_str(defaults.sharing))
    if has_sound_support:
        group.add_option("--speaker", action="store_true",
                          dest="speaker", default=defaults.speaker,
                          help="Enable forwarding of sound output to the client(s) (default: %s)" % enabled_str(defaults.speaker))
        group.add_option("--no-speaker", action="store_false",
                          dest="speaker", default=defaults.speaker,
                          help="Disable forwarding of sound output to the client(s) (default: %s)" % enabled_str(defaults.speaker))
        CODEC_HELP = """Specify the codec(s) to use for forwarding the %s sound output.
    This parameter can be specified multiple times and the order in which the codecs
    are specified defines the preferred codec order.
    Use the special value 'help' to get a list of options.
    When unspecified, all the available codecs are allowed and the first one is used."""
        group.add_option("--speaker-codec", action="append",
                          dest="speaker_codec", default=list(defaults.speaker_codec or []),
                          help=CODEC_HELP % "speaker")
        group.add_option("--microphone", action="store_true",
                          dest="microphone", default=defaults.microphone,
                          help="Enable forwarding of sound input to the server (default: %s)" % enabled_str(defaults.microphone))
        group.add_option("--no-microphone", action="store_false",
                          dest="microphone", default=defaults.microphone,
                          help="Disable forwarding of sound input to the server (default: %s)" % enabled_str(defaults.microphone))
        group.add_option("--microphone-codec", action="append",
                          dest="microphone_codec", default=list(defaults.microphone_codec or []),
                          help=CODEC_HELP % "microphone")
    else:
        hidden_options["speaker"] = "no"
        hidden_options["speaker_codec"] = []
        hidden_options["microphone"] = "no"
        hidden_options["microphone_codec"] = []

    group = optparse.OptionGroup(parser, "Encoding and Compression Options",
                "These options are used by the client to specify the desired picture and network data compression."
                "They may also be specified on the server as default values for those clients that do not set them.")
    parser.add_option_group(group)
    group.add_option("--encodings", action="store",
                      dest="encodings", default=defaults.encodings,
                      help="Specify which encodings are allowed (default: %default)")
    group.add_option("--encoding", action="store",
                      metavar="ENCODING", default=defaults.encoding,
                      dest="encoding", type="str",
                      help="Which image compression algorithm to use, specify 'help' to get a list of options."
                            " Default: %default."
                      )
    if (supports_server or supports_shadow):
        group.add_option("--video-encoders", action="store",
                          dest="video_encoders", default=defaults.video_encoders,
                          help="Specify which video encoders to enable, to get a list of all the options specify 'help'")
    else:
        hidden_options["encoders"] = []
    group.add_option("--csc-modules", action="store",
                      dest="csc_modules", default=defaults.csc_modules,
                      help="Specify which colourspace conversion modules to enable, to get a list of all the options specify 'help' (default: %default)")
    group.add_option("--video-decoders", action="store",
                      dest="video_decoders", default=defaults.video_decoders,
                      help="Specify which video decoders to enable, to get a list of all the options specify 'help'")
    group.add_option("--min-quality", action="store",
                      metavar="MIN-LEVEL",
                      dest="min_quality", type="int", default=defaults.min_quality,
                      help="Sets the minimum encoding quality allowed in automatic quality setting (from 1 to 100, 0 to leave unset). Default: %default.")
    group.add_option("--quality", action="store",
                      metavar="LEVEL",
                      dest="quality", type="int", default=defaults.quality,
                      help="Use a fixed image compression quality - only relevant to lossy encodings (1-100, 0 to use automatic setting). Default: %default.")
    group.add_option("--min-speed", action="store",
                      metavar="SPEED",
                      dest="min_speed", type="int", default=defaults.min_speed,
                      help="Sets the minimum encoding speed allowed in automatic speed setting (1-100, 0 to leave unset). Default: %default.")
    group.add_option("--speed", action="store",
                      metavar="SPEED",
                      dest="speed", type="int", default=defaults.speed,
                      help="Use image compression with the given encoding speed (1-100, 0 to use automatic setting). Default: %default.")
    group.add_option("--auto-refresh-delay", action="store",
                      dest="auto_refresh_delay", type="float", default=defaults.auto_refresh_delay,
                      metavar="DELAY",
                      help="Idle delay in seconds before doing an automatic lossless refresh."
                      + " 0.0 to disable."
                      + " Default: %default.")
    group.add_option("--compressors", action="store",
                      dest="compressors", default=", ".join(defaults.compressors),
                      help="The packet compressors to enable (default: %default)")
    group.add_option("--packet-encoders", action="store",
                      dest="packet_encoders", default=", ".join(defaults.packet_encoders),
                      help="The packet encoders to enable (default: %default)")
    group.add_option("-z", "--compress", action="store",
                      dest="compression_level", type="int", default=defaults.compression_level,
                      metavar="LEVEL",
                      help="How hard to work on compressing data."
                      + " You generally do not need to use this option,"
                      + " the default value should be adequate,"
                      + " picture data is compressed separately (see --encoding)."
                      + " 0 to disable compression,"
                      + " 9 for maximal (slowest) compression. Default: %default.")

    group = optparse.OptionGroup(parser, "Client Features Options",
                "These options control client features that affect the appearance or the keyboard.")
    parser.add_option_group(group)
    group.add_option("--opengl", action="store",
                      dest="opengl", default=defaults.opengl,
                      help="Use OpenGL accelerated rendering, options: yes,no,auto. Default: %s." % print_bool("opengl", defaults.opengl))
    group.add_option("--windows", action="store_true",
                      dest="windows", default=defaults.windows,
                      help="Forward windows (default: %s)" % enabled_str(defaults.windows))
    group.add_option("--no-windows", action="store_false",
                      dest="windows", default=defaults.windows,
                      help="Do not forward windows (default: %s)" % enabled_str(defaults.windows))
    group.add_option("--session-name", action="store",
                      dest="session_name", default=defaults.session_name,
                      help="The name of this session, which may be used in notifications, menus, etc. Default: Xpra")
    group.add_option("--client-toolkit", action="store",
                      dest="client_toolkit", default=defaults.client_toolkit,
                      help="The type of client toolkit. Use the value 'help' to get a list of options. Default: %default")
    group.add_option("--window-layout", action="store",
                      dest="window_layout", default=defaults.window_layout,
                      help="The type of window layout to use, each client toolkit may provide different layouts."
                        "use the value 'help' to get a list of possible layouts. Default: %default")
    group.add_option("--border", action="store",
                      dest="border", default=defaults.border,
                      help="The border to draw inside xpra windows to distinguish them from local windows."
                        "Format: color[,size]. Default: %default")
    group.add_option("--title", action="store",
                      dest="title", default=defaults.title,
                      help="Text which is shown as window title, may use remote metadata variables (default: '%default')")
    group.add_option("--window-icon", action="store",
                          dest="window_icon", default=defaults.window_icon,
                          help="Path to the default image which will be used for all windows (the application may override this)")
    # let the platform specific code add its own options:
    # adds "--no-tray" for platforms that support it
    add_client_options(group, defaults)
    hidden_options["tray"] =  True
    hidden_options["delay_tray"] =  False
    group.add_option("--tray-icon", action="store",
                          dest="tray_icon", default=defaults.tray_icon,
                          help="Path to the image which will be used as icon for the system-tray or dock")
    group.add_option("--key-shortcut", action="append",
                      dest="key_shortcut", type="str", default=list(defaults.key_shortcut or []),
                      help="Define key shortcuts that will trigger specific actions."
                      + "If no shortcuts are defined, it defaults to '%s'" % (",".join(defaults.key_shortcut or [])))
    group.add_option("--keyboard-sync", action="store_true",
                      dest="keyboard_sync", default=defaults.keyboard_sync,
                      help="Enable keyboard state synchronization (default: %s)" % enabled_str(defaults.keyboard_sync))
    group.add_option("--no-keyboard-sync", action="store_false",
                      dest="keyboard_sync", default=defaults.keyboard_sync,
                      help="Disable keyboard state synchronization, prevents keys from repeating on high latency links but also may disrupt applications which access the keyboard directly (default: %s)" % enabled_str(defaults.keyboard_sync))

    group = optparse.OptionGroup(parser, "Advanced Options",
                "These options apply to both client and server. Please refer to the man page for details.")
    parser.add_option_group(group)
    group.add_option("--password-file", action="store",
                      dest="password_file", default=defaults.password_file,
                      help="The file containing the password required to connect (useful to secure TCP mode)")
    group.add_option("--input-method", action="store",
                      dest="input_method", default=defaults.input_method,
                      help="Which X11 input method to configure for client applications started with start-child (default: %default, options: none, keep, xim, IBus, SCIM, uim)")
    group.add_option("--dpi", action="store",
                      dest="dpi", default=defaults.dpi,
                      help="The 'dots per inch' value that client applications should try to honour (default: %default)")
    default_socket_dir_str = defaults.socket_dir or "$XPRA_SOCKET_DIR or '~/.xpra'"
    group.add_option("--socket-dir", action="store",
                      dest="socket_dir", default=defaults.socket_dir,
                      help="Directory to place/look for the socket files in (default: %s)" % default_socket_dir_str)
    group.add_option("-d", "--debug", action="store",
                      dest="debug", default=defaults.debug, metavar="FILTER1,FILTER2,...",
                      help="List of categories to enable debugging for (you can also use \"all\" or \"help\", default: '%default')")
    group.add_option("--ssh", action="store",
                      dest="ssh", default=defaults.ssh, metavar="CMD",
                      help="How to run ssh (default: '%default')")
    group.add_option("--exit-ssh", action="store_true",
                      dest="exit_ssh", default=defaults.exit_ssh,
                      help="Terminate SSH when disconnecting (default: %s)" % print_bool("exit_ssh", defaults.exit_ssh, 'terminate', 'do not terminate'))
    group.add_option("--no-exit-ssh", action="store_false",
                      dest="exit_ssh", default=defaults.exit_ssh,
                      help="Do not terminate SSH when disconnecting, this may break password authentication on some platforms (default: %s)" % print_bool("exit_ssh", defaults.exit_ssh, 'terminate', 'do not terminate'))
    group.add_option("--username", action="store",
                      dest="username", default=defaults.username,
                      help="The username supplied by the client for authentication (default: '%default')")
    group.add_option("--auth", action="store",
                      dest="auth", default=defaults.auth,
                      help="The authentication module (default: '%default')")
    group.add_option("--mmap-group", action="store_true",
                      dest="mmap_group", default=defaults.mmap_group,
                      help="When creating the mmap file with the client, set the group permission on the mmap file to the same value as the owner of the server socket file we connect to (default: '%default')")
    group.add_option("--enable-pings", action="store_true",
                      dest="pings", default=defaults.pings,
                      help="Send ping packets every second to gather latency statistics (default: %s)" % enabled_str(defaults.pings))
    group.add_option("--clipboard-filter-file", action="store",
                      dest="clipboard_filter_file", default=defaults.clipboard_filter_file,
                      help="Name of a file containing regular expressions of clipboard contents that must be filtered out")
    group.add_option("--remote-xpra", action="store",
                      dest="remote_xpra", default=defaults.remote_xpra,
                      metavar="CMD",
                      help="How to run xpra on the remote host (default: '%default')")
    group.add_option("--encryption", action="store",
                      dest="encryption", default=defaults.encryption,
                      metavar="ALGO",
                      help="Specifies the encryption cipher to use, supported algorithms are: %s (default: None)" % (", ".join(ENCRYPTION_CIPHERS) or 'none available'))
    group.add_option("--encryption-keyfile", action="store",
                      dest="encryption_keyfile", default=defaults.encryption_keyfile,
                      metavar="FILE",
                      help="Specifies the file containing the encryption key. (default: '%default')")

    options, args = parser.parse_args(cmdline[1:])

    #ensure all the option fields are set even though
    #some options are not shown to the user:
    for k,v in hidden_options.items():
        if not hasattr(options, k):
            setattr(options, k, v)

    #process "help" arguments early:
    from xpra.log import KNOWN_FILTERS
    options.debug = fixup_debug_option(options.debug)
    if options.debug:
        categories = options.debug.split(",")
        for cat in categories:
            if cat=="help":
                raise InitInfo("known logging filters (there may be others): %s" % ", ".join(KNOWN_FILTERS))

    #special case for things stored as lists, but command line option is a CSV string:
    #and may have "none" or "all" special values
    fixup_encodings(options)
    fixup_compression(options)
    fixup_packetencoding(options)
    fixup_video_all_or_none(options)

    #special handling for URL mode:
    #xpra attach xpra://[mode:]host:port/?param1=value1&param2=value2
    if len(args)==2 and args[0]=="attach" and args[1].startswith("xpra://"):
        url = args[1]
        from urlparse import urlparse, parse_qs
        up = urlparse(url)
        address = up.netloc
        qpos = url.find("?")
        if qpos>0:
            params_str = url[qpos+1:]
            params = parse_qs(params_str, keep_blank_values=True)
            f_params = {}
            #print("params=%s" % str(params))
            for k,v in params.items():
                t = OPTION_TYPES.get(k)
                if t is not None and t!=list:
                    v = v[0]
                f_params[k] = v
            v_params = validate_config(f_params)
            for k,v in v_params.items():
                setattr(options, k, v)
        al = address.lower()
        if not al.startswith(":") and not al.startswith("tcp") and not al.startswith("ssh"):
            #assume tcp if not specified
            address = "tcp:%s" % address
        args[1] = address

    try:
        int(options.dpi)
    except Exception, e:
        raise InitException("invalid dpi: %s" % e)
    if options.encryption:
        if not ENCRYPTION_CIPHERS:
            raise InitException("cannot use encryption: no ciphers available (pycrypto must be installed)")
        if options.encryption and options.encryption not in ENCRYPTION_CIPHERS:
            raise InitException("encryption %s is not supported, try: %s" % (options.encryption, ", ".join(ENCRYPTION_CIPHERS)))
        #password file can be used as fallback for encryption keys:
        has_key = options.password_file or os.environ.get('XPRA_PASSWORD') or os.environ.get('XPRA_ENCRYPTION_KEY')
        if not has_key and options.encryption and not options.encryption_keyfile:
            raise InitException("encryption %s cannot be used without a keyfile (see --encryption-keyfile option)" % options.encryption)
    #ensure opengl is either True, False or None
    options.opengl = parse_bool("opengl", options.opengl)
    return options, args

def dump_frames(*arsg):
    frames = sys._current_frames()
    print("")
    print("found %s frames:" % len(frames))
    for fid,frame in frames.items():
        print("%s - %s:" % (fid, frame))
        traceback.print_stack(frame)
    print("")


def configure_logging(options, mode):
    if mode in ("start", "upgrade", "attach", "shadow", "proxy"):
        if "help" in options.speaker_codec or "help" in options.microphone_codec:
            from xpra.sound.gstreamer_util import show_sound_codec_help
            info = show_sound_codec_help(mode!="attach", options.speaker_codec, options.microphone_codec)
            raise InitInfo("\n".join(info))
    else:
        #a bit naughty here, but it's easier to let xpra.log initialize
        #the logging system every time, and just undo things here..
        logging.root.handlers = []
        logging.root.addHandler(logging.StreamHandler(sys.stdout))

    from xpra.log import add_debug_category, add_disabled_category, enable_debug_for, disable_debug_for
    if options.debug:
        categories = options.debug.split(",")
        for cat in categories:
            if len(cat)==0:
                continue
            if cat[0]=="-":
                add_disabled_category(cat[1:])
                disable_debug_for(cat[1:])
            else:
                add_debug_category(cat)
                enable_debug_for(cat)

    #always log debug level, we just use it selectively (see above)
    logging.root.setLevel(logging.DEBUG)

    #register posix signals for debugging:
    if os.name=="posix":
        def sigusr1(*args):
            dump_frames()
        signal.signal(signal.SIGUSR1, sigusr1)


def run_mode(script_file, error_cb, options, args, mode, defaults):
    #configure default logging handler:
    if os.name=="posix" and os.getuid()==0 and mode!="proxy":
        warn("\nWarning: running as root")

    configure_logging(options, mode)

    try:
        ssh_display = len(args)>0 and (args[0].startswith("ssh/") or args[0].startswith("ssh:"))
        if mode in ("start", "shadow") and ssh_display:
            #ie: "xpra start ssh:HOST:DISPLAY --start-child=xterm"
            return run_remote_server(error_cb, options, args, mode, defaults)
        elif (mode in ("start", "upgrade", "proxy") and supports_server) or (mode=="shadow" and supports_shadow):
            nox()
            from xpra.scripts.server import run_server
            return run_server(error_cb, options, mode, script_file, args)
        elif mode in ("attach", "detach", "screenshot", "version", "info", "control", "_monitor"):
            return run_client(error_cb, options, args, mode)
        elif mode in ("stop", "exit") and (supports_server or supports_shadow):
            nox()
            return run_stopexit(mode, error_cb, options, args)
        elif mode == "list" and (supports_server or supports_shadow):
            return run_list(error_cb, options, args)
        elif mode in ("_proxy", "_proxy_start", "_shadow_start") and (supports_server or supports_shadow):
            nox()
            return run_proxy(error_cb, options, script_file, args, mode, defaults)
        elif mode == "initenv":
            from xpra.scripts.server import xpra_runner_shell_script, write_runner_shell_script
            script = xpra_runner_shell_script(script_file, os.getcwd(), options.socket_dir)
            dotxpra = DotXpra(options.socket_dir)
            write_runner_shell_script(dotxpra, script, False)
            return 0
        else:
            error_cb("invalid mode '%s'" % mode)
            return 1
    except KeyboardInterrupt, e:
        sys.stderr.write("\ncaught %s, exiting\n" % repr(e))
        return 128+signal.SIGINT


def parse_display_name(error_cb, opts, display_name):
    desc = {"display_name" : display_name}
    if display_name.lower().startswith("ssh:") or display_name.lower().startswith("ssh/"):
        separator = display_name[3] # ":" or "/"
        desc["type"] = "ssh"
        desc["proxy_command"] = ["_proxy"]
        desc["local"] = False
        desc["exit_ssh"] = opts.exit_ssh
        parts = display_name.split(separator)
        if len(parts)>2:
            #ssh:HOST:DISPLAY or ssh/HOST/DISPLAY
            host = separator.join(parts[1:-1])
            display = ":" + parts[-1]
            desc["display"] = display
            opts.display = display
            desc["display_as_args"] = [display]
        else:
            #ssh:HOST or ssh/HOST
            host = parts[1]
            desc["display"] = None
            desc["display_as_args"] = []
        #ie: ssh=["/usr/bin/ssh", "-v"]
        ssh = shlex.split(opts.ssh)
        desc["ssh"] = ssh
        full_ssh = ssh

        #maybe restrict to win32 only?
        #sys.platform.startswith("win")
        ssh_cmd = ssh[0].lower()
        is_putty = ssh_cmd.endswith("plink") or ssh_cmd.endswith("plink.exe")
        if is_putty:
            #putty needs those:
            full_ssh.append("-ssh")
            full_ssh.append("-agent")

        upos = host.find("@")
        if upos>=0:
            #HOST=username@host
            username = host[:upos]
            host = host[upos+1:]
            ppos = username.find(":")
            if ppos>=0:
                password = username[ppos+1:]
                username = username[:ppos]
                desc["password"] = password
                if password and is_putty:
                    full_ssh += ["-pw", password]
            if username:
                desc["username"] = username
                opts.username = username
                full_ssh += ["-l", username]
        upos = host.rfind(":")
        ssh_port = ""
        if host.count(":")>=2:
            #more than 2 ":", assume this is IPv6:
            if host.startswith("["):
                #if we have brackets, we can support: "[HOST]:SSHPORT"
                epos = host.find("]")
                if epos<0:
                    error_cb("invalid host format, expected IPv6 [..]")
                ssh_port = host[epos+1:]            #ie: ":SSHPORT"
                if ssh_port.startswith(":"):
                    ssh_port = ssh_port[1:]         #ie: "SSHPORT"
                host = host[1:epos]                 #ie: "HOST"
            else:
                #otherwise, we have to assume they are all part of IPv6
                #we could count them at split at 8, but that would be just too fugly
                pass
        elif upos>0:
            #assume HOST:SSHPORT
            ssh_port = host[upos+1:]
            host = host[:upos]
        if ssh_port:
            try:
                desc["port"] = int(ssh_port)
            except:
                error_cb("invalid ssh port specified: %s" % ssh_port)
            #grr why bother doing it different?
            if is_putty:
                full_ssh += ["-P", ssh_port]
            else:
                full_ssh += ["-p", ssh_port]

        full_ssh += ["-T", host]
        desc["host"] = host
        desc["full_ssh"] = full_ssh
        remote_xpra = opts.remote_xpra.split()
        if opts.socket_dir:
            #ie: XPRA_SOCKET_DIR=/tmp .xpra/run-xpra _proxy :10
            remote_xpra.append("--socket-dir=%s" % opts.socket_dir)
        desc["remote_xpra"] = remote_xpra
        if desc.get("password") is None and opts.password_file and os.path.exists(opts.password_file):
            try:
                try:
                    passwordFile = open(opts.password_file, "rb")
                    desc["password"] = passwordFile.read()
                finally:
                    passwordFile.close()
            except Exception, e:
                print("failed to read password file %s: %s", opts.password_file, e)
        return desc
    elif display_name.startswith(":"):
        desc["type"] = "unix-domain"
        desc["local"] = True
        desc["display"] = display_name
        opts.display = display_name
        desc["socket_dir"] = osexpand(opts.socket_dir or get_default_socket_dir(), opts.username)
        return desc
    elif display_name.startswith("tcp:") or display_name.startswith("tcp/"):
        separator = display_name[3] # ":" or "/"
        desc["type"] = "tcp"
        desc["local"] = False
        parts = display_name.split(separator)
        if len(parts) not in (3, 4):
            error_cb("invalid tcp connection string, use tcp/[username@]host/port[/display] or tcp:[username@]host:port[:display]")
        #display (optional):
        if len(parts)==4:
            display = parts[3]
            if display:
                try:
                    v = int(display)
                    display = ":%s" % v
                except:
                    pass
                desc["display"] = display
                opts.display = display
        #port:
        port = parts[2]
        try:
            port = int(port)
        except:
            error_cb("invalid port, not a number: %s" % port)
        if port<=0 or port>=65536:
            error_cb("invalid port number: %s" % port)
        desc["port"] = port
        #host:
        host = parts[1]
        if host.find("@")>0:
            username, host = host.split("@", 1)
            if username:
                desc["username"] = username
                opts.username = username
        if host == "":
            host = "127.0.0.1"
        desc["host"] = host
        return desc
    else:
        error_cb("unknown format for display name: %s" % display_name)

def pick_display(error_cb, opts, extra_args):
    if len(extra_args) == 0:
        # Pick a default server
        sockdir = DotXpra(opts.socket_dir or get_default_socket_dir())
        servers = sockdir.sockets()
        live_servers = [display
                        for (state, display) in servers
                        if state is DotXpra.LIVE]
        if len(live_servers) == 0:
            if not LOCAL_SERVERS_SUPPORTED:
                error_cb("this installation does not support local servers, you must specify a remote display")
            error_cb("cannot find a live server to connect to")
        elif len(live_servers) == 1:
            return parse_display_name(error_cb, opts, live_servers[0])
        else:
            error_cb("there are multiple servers running, please specify")
    elif len(extra_args) == 1:
        return parse_display_name(error_cb, opts, extra_args[0])
    else:
        error_cb("too many arguments")

def _socket_connect(sock, endpoint, description, dtype):
    sock.connect(endpoint)
    sock.settimeout(None)
    return SocketConnection(sock, sock.getsockname(), sock.getpeername(), description, dtype)

def connect_or_fail(display_desc):
    try:
        return connect_to(display_desc)
    except Exception, e:
        raise InitException("connection failed: %s" % e)

def ssh_connect_failed(message):
    #by the time ssh fails, we may have entered the gtk main loop
    #(and more than once thanks to the clipboard code..)
    from xpra.gtk_common.quit import gtk_main_quit_really
    gtk_main_quit_really()

def connect_to(display_desc, debug_cb=None, ssh_fail_cb=ssh_connect_failed):
    display_name = display_desc["display_name"]
    dtype = display_desc["type"]
    conn = None
    if dtype == "ssh":
        cmd = display_desc["full_ssh"]
        proxy_cmd = display_desc["remote_xpra"] + display_desc["proxy_command"] + display_desc["display_as_args"]
        cmd += ["xpra initenv || echo \"Warning: xpra server does not support initenv\" 1>&2;"+(" ".join(proxy_cmd))]
        try:
            kwargs = {}
            kwargs["stderr"] = sys.stderr
            if not display_desc.get("exit_ssh", False) and os.name=="posix" and not sys.platform.startswith("darwin"):
                def setsid():
                    #run in a new session
                    os.setsid()
                kwargs["preexec_fn"] = setsid
            elif sys.platform.startswith("win"):
                from subprocess import CREATE_NEW_PROCESS_GROUP, CREATE_NEW_CONSOLE
                flags = CREATE_NEW_PROCESS_GROUP | CREATE_NEW_CONSOLE
                kwargs["creationflags"] = flags
                kwargs["stderr"] = PIPE
            if debug_cb:
                debug_cb("starting %s tunnel" % str(cmd[0]))
                #debug_cb("starting ssh: %s with kwargs=%s" % (str(cmd), kwargs))
            child = Popen(cmd, stdin=PIPE, stdout=PIPE, **kwargs)
        except OSError, e:
            raise Exception("Error running ssh program '%s': %s" % (cmd, e))
        def abort_test(action):
            """ if ssh dies, we don't need to try to read/write from its sockets """
            e = child.poll()
            if e is not None:
                error_message = "cannot %s using %s: the SSH process has terminated with exit code=%s" % (action, display_desc["full_ssh"], e)
                if debug_cb:
                    debug_cb(error_message)
                if ssh_fail_cb:
                    ssh_fail_cb(error_message)
                if "ssh_abort" not in display_desc:
                    display_desc["ssh_abort"] = True
                    from xpra.log import Logger
                    log = Logger()
                    log.error("The SSH process has terminated with exit code %s", e)
                    if conn.input_bytecount==0 and conn.output_bytecount==0:
                        log.error("Connection to the xpra server via SSH failed for: %s", display_name)
                        log.error(" the command line used was: %s", cmd)
                        log.error(" check your username, hostname, display number, etc")
                raise ConnectionClosedException(error_message)
        def stop_tunnel():
            if os.name=="posix":
                #on posix, the tunnel may be shared with other processes
                #so don't kill it... which may leave it behind after use.
                #but at least make sure we close all the pipes:
                for name,fd in {"stdin" : child.stdin,
                                "stdout" : child.stdout,
                                "stderr" : child.stderr}.items():
                    try:
                        if fd:
                            fd.close()
                    except Exception, e:
                        print("error closing ssh tunnel %s: %s" % (name, e))
                if not display_desc.get("exit_ssh", False):
                    #leave it running
                    return
            try:
                if child.poll() is None:
                    #only supported on win32 since Python 2.7
                    if hasattr(child, "terminate"):
                        child.terminate()
                    elif hasattr(os, "kill"):
                        os.kill(child.pid, signal.SIGTERM)
                    else:
                        raise Exception("cannot find function to kill subprocess")
            except Exception, e:
                print("error trying to stop ssh tunnel process: %s" % e)
        conn = TwoFileConnection(child.stdin, child.stdout, abort_test, target=display_name, info=dtype, close_cb=stop_tunnel)
        conn.timeout = 0            #taken care of by abort_test

    elif dtype == "unix-domain":
        if not hasattr(socket, "AF_UNIX"):
            return False, "unix domain sockets are not available on this operating system"
        sockdir = DotXpra(display_desc["socket_dir"])
        sock = socket.socket(socket.AF_UNIX)
        sock.settimeout(SOCKET_TIMEOUT)
        sockfile = sockdir.socket_path(display_desc["display"])
        conn = _socket_connect(sock, sockfile, display_name, dtype)
        conn.timeout = SOCKET_TIMEOUT

    elif dtype == "tcp":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(SOCKET_TIMEOUT)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, TCP_NODELAY)
        tcp_endpoint = (display_desc["host"], display_desc["port"])
        conn = _socket_connect(sock, tcp_endpoint, display_name, dtype)
        conn.timeout = SOCKET_TIMEOUT

    else:
        assert False, "unsupported display type in connect: %s" % dtype
    return conn


def run_client(error_cb, opts, extra_args, mode):
    if mode=="screenshot":
        if len(extra_args)==0:
            error_cb("invalid number of arguments for screenshot mode")
        screenshot_filename = extra_args[0]
        extra_args = extra_args[1:]

    if opts.compression_level < 0 or opts.compression_level > 9:
        error_cb("Compression level must be between 0 and 9 inclusive.")
    if opts.quality!=-1 and (opts.quality < 0 or opts.quality > 100):
        error_cb("Quality must be between 0 and 100 inclusive. (or -1 to disable)")

    def connect():
        return connect_or_fail(pick_display(error_cb, opts, extra_args))

    if mode=="screenshot":
        from xpra.client.gobject_client_base import ScreenshotXpraClient
        app = ScreenshotXpraClient(connect(), opts, screenshot_filename)
    elif mode=="info":
        from xpra.client.gobject_client_base import InfoXpraClient
        app = InfoXpraClient(connect(), opts)
    elif mode=="_monitor":
        from xpra.client.gobject_client_base import MonitorXpraClient
        app = MonitorXpraClient(connect(), opts)
    elif mode=="control":
        from xpra.client.gobject_client_base import ControlXpraClient
        if len(extra_args)<=1:
            error_cb("not enough arguments for 'control' mode")
        args = extra_args[1:]
        extra_args = extra_args[:1]
        app = ControlXpraClient(connect(), opts)
        app.set_command_args(args)
    elif mode=="version":
        from xpra.client.gobject_client_base import VersionXpraClient
        app = VersionXpraClient(connect(), opts)
    elif mode=="detach":
        from xpra.client.gobject_client_base import DetachXpraClient
        app = DetachXpraClient(connect(), opts)
    else:
        try:
            from xpra.platform.gui import init as gui_init
            gui_init()
            app = make_client(error_cb, opts)
        except RuntimeError, e:
            #exceptions at this point are still initialization exceptions
            raise InitException(e.message)
        layouts = app.get_supported_window_layouts() or ["default"]
        layouts_str = ", ".join(layouts)
        if opts.window_layout and opts.window_layout.lower()=="help":
            raise InitInfo("%s supports the following layouts: %s" % (app.client_toolkit(), layouts_str))
        if opts.window_layout and opts.window_layout not in layouts:
            error_cb("window layout '%s' is not supported by the %s toolkit, valid options are: %s" % (opts.window_layout, app.client_toolkit(), layouts_str))
        app.init(opts)
        if opts.encoding:
            #fix old encoding names if needed:
            err = opts.encoding not in app.get_encodings()
            info = ""
            if err and opts.encoding!="help":
                info = "invalid encoding: %s\n" % opts.encoding
            if opts.encoding=="help" or err:
                from xpra.codecs.loader import encodings_help
                raise InitInfo(info+"%s xpra client supports the following encodings:\n * %s" % (app.client_toolkit(), "\n * ".join(encodings_help(app.get_encodings()))))
        def handshake_complete(*args):
            from xpra.log import Logger
            log = Logger()
            log.info("Attached to %s (press Control-C to detach)\n" % conn.target)
        if hasattr(app, "connect"):
            app.connect("handshake-complete", handshake_complete)
        app.init_ui(opts, extra_args)
        try:
            conn = connect()
            #UGLY warning: connect will parse the display string,
            #which may change the username..
            app.username = opts.username
            app.setup_connection(conn)
        except Exception, e:
            app.cleanup()
            raise e
    return do_run_client(app)

def make_client(error_cb, opts):
    app = None
    if not opts.client_toolkit:
        from xpra.gtk_common.gobject_compat import import_gobject, is_gtk3
        import_gobject()
        if is_gtk3():
            opts.client_toolkit = "gtk3"
        else:
            opts.client_toolkit = "gtk2"

    ct = opts.client_toolkit.lower()
    toolkits = {}
    def check_toolkit(*modules):
        try:
            for x in modules:
                __import__(x, {}, {}, [])
            return True
        except:
            return False

    if check_toolkit("gtk.gdk", "xpra.client.gtk2"):
        toolkits["gtk2"] = "xpra.client.gtk2.client"
    elif check_toolkit("gi", "xpra.client.gtk3"):
        toolkits["gtk3"] = "xpra.client.gtk3.client"
    if check_toolkit("PyQt4.QtCore", "PyQt4.QtGui", "xpra.client.qt4"):
        toolkits["qt4"] = "xpra.client.qt4.client"

    if len(toolkits)==0:
        error_cb("no client toolkit found! (maybe this is a server-only installation?)")
    if ct=="help":
        error_cb("The following client toolkits are available: %s" % (", ".join(toolkits.keys())))
    client_module = toolkits.get(ct)
    if client_module is None:
        error_cb("invalid client toolkit: %s, try one of: %s" % (
                    opts.client_toolkit, ", ".join(toolkits.keys())))
    toolkit_module = __import__(client_module, globals(), locals(), ['XpraClient'])
    if toolkit_module is None:
        error_cb("could not load %s" % client_module)
    return toolkit_module.XpraClient()

def do_run_client(app):
    try:
        try:
            return app.run()
        except KeyboardInterrupt:
            return -signal.SIGINT
    finally:
        app.cleanup()

def shellquote(s):
    return '"' + s.replace('"', '\\"') + '"'

def strip_defaults_start_child(start_child, defaults_start_child):
    if start_child and defaults_start_child:
        #ensure we don't pass start-child commands
        #which came from defaults (the configuration files)
        #only the ones specified on the command line:
        #(and only remove them once so the command line can re-add the same ones!)
        for x in defaults_start_child:
            if x in start_child:
                start_child.remove(x)
    return start_child

def run_remote_server(error_cb, opts, args, mode, defaults):
    """ Uses the regular XpraClient with patched proxy arguments to tell run_proxy to start the server """
    params = parse_display_name(error_cb, opts, args[0])
    #add special flags to "display_as_args"
    proxy_args = []
    if params["display"] is not None:
        proxy_args.append(params["display"])
    if opts.start_child:
        start_child = strip_defaults_start_child(opts.start_child, defaults.start_child)
        for c in start_child:
            proxy_args.append(shellquote("--start-child=%s" % c))
    #key=value options we forward:
    for x in ("session-name", "encoding", "socket-dir", "dpi"):
        v = getattr(opts, x.replace("-", "_"))
        if v:
            proxy_args.append("--%s=%s" % (x, v))
    #these options must be enabled explicitly (no disable option for most of them):
    for e in ("exit-with-children", "mmap-group", "readonly"):
        if getattr(opts, e.replace("-", "_")) is True:
            proxy_args.append("--%s" % e)
    #older versions only support disabling:
    for e in ("pulseaudio", "mmap",
              "system-tray", "clipboard", "bell"):
        if getattr(opts, e.replace("-", "_")) is False:
            proxy_args.append("--no-%s" % e)
    params["display_as_args"] = proxy_args
    #and use _proxy_start subcommand:
    if mode=="shadow":
        params["proxy_command"] = ["_shadow_start"]
    else:
        assert mode=="start"
        params["proxy_command"] = ["_proxy_start"]
    app = make_client(error_cb, opts)
    app.init(opts)
    app.init_ui(opts)
    conn = connect_or_fail(params)
    app.setup_connection(conn)
    do_run_client(app)

def find_X11_displays(max_display_no=10):
    displays = []
    X11_SOCKET_DIR = "/tmp/.X11-unix/"
    if os.path.exists(X11_SOCKET_DIR) and os.path.isdir(X11_SOCKET_DIR):
        for x in os.listdir(X11_SOCKET_DIR):
            if not x.startswith("X"):
                continue
            try:
                v = int(x[1:])
                #arbitrary: only shadow automatically displays below 10..
                if v<max_display_no:
                    displays.append(v)
                #check that this is a socket
                socket_path = os.path.join(X11_SOCKET_DIR, x)
                mode = os.stat(socket_path).st_mode
                is_socket = stat.S_ISSOCK(mode)
                if not is_socket:
                    continue
            except:
                pass
    return displays

def guess_xpra_display(socket_dir):
    sockdir = DotXpra(socket_dir)
    results = sockdir.sockets()
    live = [display for state, display in results if state==DotXpra.LIVE]
    assert len(live)>0, "no existing xpra servers found"
    assert len(live)<=1, "too many existing xpra servers found, cannot guess which one to use"
    return live[0]

def guess_X11_display(socket_dir):
    displays = [":%s" % x for x in find_X11_displays()]
    assert len(displays)!=0, "could not detect any live X11 displays"
    if len(displays)>1:
        #since we are here to shadow,
        #assume we want to shadow a real X11 server,
        #so remove xpra's own displays to narrow things down:
        sockdir = DotXpra(socket_dir)
        results = sockdir.sockets()
        xpra_displays = [display for _, display in results]
        displays = list(set(displays)-set(xpra_displays))
        assert len(displays)!=0, "could not detect any live plain X11 displays, only multiple xpra displays: %s" % ", ".join(xpra_displays)
    assert len(displays)==1, "too many live X11 displays to choose from: %s" % ", ".join(displays)
    return displays[0]

def run_proxy(error_cb, opts, script_file, args, mode, defaults):
    from xpra.server.proxy import XpraProxy
    assert "gtk" not in sys.modules
    if mode in ("_proxy_start", "_shadow_start"):
        #we must use a subprocess to avoid messing things up - yuk
        cmd = [script_file]
        if mode=="_proxy_start":
            cmd.append("start")
            assert len(args)==1, "_proxy_start: expected 1 argument but got %s: %s" % (len(args), args)
            display_name = args[0]
        else:
            assert mode=="_shadow_start"
            cmd.append("shadow")
            if len(args)==1:
                #display_name was provided:
                display_name = args[0]
            else:
                assert len(args)==0, "_shadow_start: expected 0 or 1 arguments but got %s: %s" % (len(args), args)
                display_name = guess_X11_display(opts.socket_dir)
                #we now know the display name, so add it:
                args = [display_name]
        #adds the display to proxy start command:
        cmd += args
        start_child = strip_defaults_start_child(opts.start_child, defaults.start_child)
        if start_child:
            for x in start_child:
                cmd.append("--start-child=%s" % x)
        if opts.exit_with_children:
            cmd.append("--exit-with-children")
        if opts.exit_with_client or mode=="_shadow_start":
            cmd.append("--exit-with-client")
        def setsid():
            os.setsid()
        proc = Popen(cmd, preexec_fn=setsid, shell=False, close_fds=True)
        dotxpra = DotXpra()
        start = time.time()
        while dotxpra.server_state(display_name, 1)!=DotXpra.LIVE:
            if time.time()-start>15:
                warn("server failed to start after %.1f seconds - sorry!" % (time.time()-start))
                return
            time.sleep(0.10)
        #start a thread just to reap server startup process (yuk)
        #(as the server process will exit as it daemonizes)
        def reaper():
            proc.wait()
        from xpra.daemon_thread import make_daemon_thread
        make_daemon_thread(reaper, "server-startup-reaper").start()
    server_conn = connect_or_fail(pick_display(error_cb, opts, args))
    app = XpraProxy(TwoFileConnection(sys.stdout, sys.stdin, info="stdin/stdout"), server_conn)
    signal.signal(signal.SIGINT, app.quit)
    signal.signal(signal.SIGTERM, app.quit)
    app.run()
    return  0

def run_stopexit(mode, error_cb, opts, extra_args):
    assert "gtk" not in sys.modules

    def show_final_state(display):
        sockdir = DotXpra(opts.socket_dir)
        for _ in range(6):
            final_state = sockdir.server_state(display)
            if final_state is DotXpra.LIVE:
                time.sleep(0.5)
        if final_state is DotXpra.DEAD:
            print("xpra at %s has exited." % display)
            return 0
        elif final_state is DotXpra.UNKNOWN:
            print("How odd... I'm not sure what's going on with xpra at %s" % display)
            return 1
        elif final_state is DotXpra.LIVE:
            print("Failed to shutdown xpra at %s" % display)
            return 1
        else:
            assert False, "invalid state: %s" % final_state
            return 1

    display_desc = pick_display(error_cb, opts, extra_args)
    conn = connect_or_fail(display_desc)
    app = None
    e = 1
    try:
        if mode=="stop":
            from xpra.client.gobject_client_base import StopXpraClient
            app = StopXpraClient(conn, opts)
        elif mode=="exit":
            from xpra.client.gobject_client_base import ExitXpraClient
            app = ExitXpraClient(conn, opts)
        else:
            raise Exception("invalid mode: %s" % mode)
        e = app.run()
    finally:
        if app:
            app.cleanup()
    if display_desc["local"]:
        show_final_state(display_desc["display"])
    else:
        print("Sent shutdown command")
    return  e


def may_cleanup_socket(sockdir, state, display, clean_states=[DotXpra.DEAD]):
    sys.stdout.write("\t%s session at %s" % (state, display))
    if state in clean_states:
        try:
            os.unlink(sockdir.socket_path(display))
        except OSError:
            pass
        else:
            sys.stdout.write(" (cleaned up)")
    sys.stdout.write("\n")

def run_list(error_cb, opts, extra_args):
    assert "gtk" not in sys.modules
    if extra_args:
        error_cb("too many arguments for mode")
    sockdir = DotXpra(opts.socket_dir)
    results = sockdir.sockets()
    if not results:
        error_cb("No xpra sessions found")
    sys.stdout.write("Found the following xpra sessions:\n")
    for state, display in results:
        may_cleanup_socket(sockdir, state, display)
    #now, re-probe the "unknown" ones:
    unknown = [display for state, display in results if state==DotXpra.UNKNOWN]
    if len(unknown)>0:
        sys.stdout.write("Re-probing unknown sessions: %s\n" % (", ".join(unknown)))
    counter = 0
    while len(unknown)>0 and counter<5:
        time.sleep(1)
        counter += 1
        probe_list = list(unknown)
        unknown = []
        for display in probe_list:
            state = sockdir.server_state(display)
            if state is DotXpra.DEAD:
                may_cleanup_socket(sockdir, state, display)
            elif state is DotXpra.UNKNOWN:
                unknown.append(display)
            else:
                sys.stdout.write("\t%s session at %s\n" % (state, display))
    #now cleanup those still unknown:
    clean_states = [DotXpra.DEAD, DotXpra.UNKNOWN]
    for display in unknown:
        state = sockdir.server_state(display)
        may_cleanup_socket(sockdir, state, display, clean_states=clean_states)
    return 0


if __name__ == "__main__":
    code = main("xpra.exe", sys.argv)
    if not code:
        code = 0
    sys.exit(code)
