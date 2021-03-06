#!/usr/bin/env python
# This file is part of Xpra.
# Copyright (C) 2010-2016 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import sys
import os

#this is here so we can expose the python "platform" module
#before we import xpra.platform
import platform as python_platform
assert python_platform
from xpra.util import AdHocStruct

def warn(msg):
    sys.stderr.write(msg+"\n")

def debug(*args):
    #can be overriden
    pass


class InitException(Exception):
    pass
class InitInfo(Exception):
    pass
class InitExit(Exception):
    def __init__(self, status, msg):
        self.status = status
        Exception.__init__(self, msg)


DEFAULT_XPRA_CONF_FILENAME = os.environ.get("XPRA_CONF_FILENAME", 'xpra.conf')
DEFAULT_NET_WM_NAME = os.environ.get("XPRA_NET_WM_NAME", "Xpra")

DEFAULT_POSTSCRIPT_PRINTER = os.environ.get("XPRA_POSTSCRIPT_PRINTER", "drv:///sample.drv/generic.ppd")

POSIX = os.name=="posix"
WIN32 = sys.platform.startswith("win")
OSX = sys.platform.startswith("darwin")
PYTHON3 = sys.version_info[0]>=3


_has_sound_support = None
def has_sound_support():
    global _has_sound_support
    if _has_sound_support is None:
        try:
            import xpra.sound
            _has_sound_support = bool(xpra.sound)
        except:
            _has_sound_support = False
    return _has_sound_support


def get_xorg_bin():
    # Detect Xorg Binary
    for p in (
              "/usr/libexec/Xorg",              #fedora 22+
              "/usr/lib/xorg/Xorg",             #ubuntu 16.10
              "/usr/lib/xorg-server/Xorg",      #arch linux
              "/usr/X11/bin/X",                 #OSX
              ):
        if os.path.exists(p):
            return p
    #look for it in $PATH:
    for x in os.environ.get("PATH").split(os.pathsep):
        xorg = os.path.join(x, "Xorg")
        if os.path.isfile(xorg):
            return xorg
    return None


def get_Xdummy_command(xorg_cmd="Xorg", log_dir="${XPRA_LOG_DIR}", xorg_conf="/etc/xpra/xorg.conf"):
    cmd = [xorg_cmd]    #ie: ["Xorg"] or ["xpra_Xdummy"] or ["./install/bin/xpra_Xdummy"]
    cmd += [
          "-noreset",
          "-nolisten", "tcp",
          "+extension", "GLX",
          "+extension", "RANDR",
          "+extension", "RENDER",
          "-auth", "$XAUTHORITY",
          "-logfile", "%s/Xorg.${DISPLAY}.log" % log_dir,
          #must be specified with some Xorg versions (ie: arch linux)
          #this directory can store xorg config files, it does not need to be created:
          "-configdir", "${HOME}/.xpra/xorg.conf.d",
          "-config", xorg_conf
          ]
    return cmd

def get_Xvfb_command():
    cmd = ["Xvfb",
           "+extension", "Composite",
           "-screen", "0", "5760x2560x24+32",
           #better than leaving to vfb after a resize?
           "-dpi", "96",
           "-nolisten", "tcp",
           "-noreset",
           "-auth", "$XAUTHORITY"
           ]
    return cmd

def detect_xvfb_command(conf_dir="/etc/xpra/", bin_dir=None, Xdummy_ENABLED=None, Xdummy_wrapper_ENABLED=None):
    #returns the xvfb command to use
    if WIN32:
        return ""
    if OSX:
        return get_Xvfb_command()
    if sys.platform.find("bsd")>=0 and Xdummy_ENABLED is None:
        warn("Warning: sorry, no support for Xdummy on %s" % sys.platform)
        return get_Xvfb_command()

    xorg_bin = get_xorg_bin()
    def Xorg_suid_check():
        if Xdummy_wrapper_ENABLED is not None:
            #honour what was specified:
            use_wrapper = Xdummy_wrapper_ENABLED
        elif not xorg_bin:
            warn("Warning: Xorg binary not found, assuming the wrapper is needed!")
            use_wrapper = True
        else:
            #Fedora 21+ workaround:
            if os.path.exists("/usr/libexec/Xorg.wrap"):
                #we need our own wrapper to bypass all the scripts and wrappers Fedora uses
                use_wrapper = True
            else:
                #auto-detect
                import stat
                xorg_stat = os.stat(xorg_bin)
                if (xorg_stat.st_mode & stat.S_ISUID)!=0:
                    if (xorg_stat.st_mode & stat.S_IROTH)==0:
                        warn("%s is suid and not readable, Xdummy support unavailable" % xorg_bin)
                        return get_Xvfb_command()
                    debug("%s is suid and readable, using the xpra_Xdummy wrapper" % xorg_bin)
                    use_wrapper = True
                else:
                    use_wrapper = False
        xorg_conf = os.path.join(conf_dir, "xorg.conf")
        if use_wrapper:
            xorg_cmd = "xpra_Xdummy"
        else:
            xorg_cmd = xorg_bin or "Xorg"
        #so we can run from install dir:
        if bin_dir and os.path.exists(os.path.join(bin_dir, xorg_cmd)):
            if bin_dir not in ("/usr/bin", "/bin"):
                xorg_cmd = os.path.join(bin_dir, xorg_cmd)
        return get_Xdummy_command(xorg_cmd, xorg_conf=xorg_conf)

    if Xdummy_ENABLED is False:
        return get_Xvfb_command()
    elif Xdummy_ENABLED is True:
        return Xorg_suid_check()
    else:
        debug("Xdummy support unspecified, will try to detect")

    from xpra.os_util import is_Ubuntu, getUbuntuVersion
    if is_Ubuntu():
        rnum = getUbuntuVersion()
        if rnum==[16, 10]:
            return Xorg_suid_check()
        debug("Warning: Ubuntu breaks Xorg/Xdummy usage - using Xvfb fallback")
        return get_Xvfb_command()
    return Xorg_suid_check()


def OpenGL_safety_check():
    #Ubuntu 12.04 will just crash on you if you try:
    from xpra.os_util import is_Ubuntu, getUbuntuVersion
    if is_Ubuntu():
        rnum = getUbuntuVersion()
        if rnum<=[12, 4]:
            return "Ubuntu %s is too buggy" % rnum
    #try to detect VirtualBox:
    #based on the code found here:
    #http://spth.virii.lu/eof2/articles/WarGame/vboxdetect.html
    #because it used to cause hard VM crashes when we probe the GL driver!
    try:
        from ctypes import cdll
        if cdll.LoadLibrary("VBoxHook.dll"):
            return "VirtualBox is present (VBoxHook.dll)"
    except:
        pass
    try:
        try:
            f = None
            f = open("\\\\.\\VBoxMiniRdrDN", "r")
        finally:
            if f:
                f.close()
                return True, "VirtualBox is present (VBoxMiniRdrDN)"
    except Exception as e:
        import errno
        if e.args[0]==errno.EACCES:
            return "VirtualBox is present (VBoxMiniRdrDN)"
    return None

OPENGL_DEFAULT = None       #will auto-detect by probing
def get_opengl_default():
    global OPENGL_DEFAULT
    if OpenGL_safety_check() is not None:
        OPENGL_DEFAULT = False
    return OPENGL_DEFAULT


def get_build_info():
    info = []
    try:
        from xpra.src_info import REVISION, LOCAL_MODIFICATIONS             #@UnresolvedImport
        try:
            mods = int(LOCAL_MODIFICATIONS)
        except:
            mods = 0
        if mods==0:
            info.append("revision %s" % REVISION)
        else:
            info.append("revision %s with %s local changes" % (REVISION, LOCAL_MODIFICATIONS))
    except Exception as e:
        warn("Error: could not find the source information: %s" % e)
    try:
        from xpra.build_info import BUILT_BY, BUILT_ON, BUILD_DATE, CYTHON_VERSION, COMPILER_VERSION    #@UnresolvedImport
        info.append("Built on %s by %s" % (BUILT_ON, BUILT_BY))
        if BUILD_DATE:
            info.append(BUILD_DATE)
        if CYTHON_VERSION!="unknown" or COMPILER_VERSION!="unknown":
            info.append("")
        if CYTHON_VERSION!="unknown":
            info.append("built with Cython %s" % CYTHON_VERSION)
        if COMPILER_VERSION!="unknown":
            cv = COMPILER_VERSION.replace("Optimizing Compiler Version", "Optimizing Compiler\nVersion")
            info += cv.splitlines()
    except Exception as e:
        warn("Error: could not find the build information: %s" % e)
    return info


def name_to_field(name):
    return name.replace("-", "_")

def save_config(conf_file, config, keys, extras_types={}):
    with open(conf_file, "w") as f:
        option_types = OPTION_TYPES.copy()
        option_types.update(extras_types)
        saved = {}
        for key in keys:
            assert key in option_types, "invalid configuration key: %s" % key
            v = getattr(config, name_to_field(key))
            saved[key] = v
            f.write("%s=%s%s" % (key, v, os.linesep))
        debug("save_config: saved %s to %s", saved, conf_file)

def read_config(conf_file):
    """
        Parses a config file into a dict of strings.
        If the same key is specified more than once,
        the value for this key will be an array of strings.
    """
    d = {}
    if not os.path.isfile(conf_file):
        debug("read_config(%s) is not a file!", conf_file)
        return d
    with open(conf_file, "rU") as f:
        lines = []
        no = 0
        for line in f:
            sline = line.strip().rstrip('\r\n').strip()
            no += 1
            if len(sline) == 0:
                debug("%4s empty line", no)
                continue
            if sline[0] in ( '!', '#' ):
                debug("%4s skipping comments   : %s", no, sline[:16]+"..")
                continue
            debug("%4s loaded              : %s", no, sline)
            lines.append(sline)
    debug("loaded %s lines", len(lines))
    #aggregate any lines with trailing backslash
    agg_lines = []
    l = ""
    for line in lines:
        if line.endswith("\\"):
            l += line[:-1]+" "
        else:
            l += line
            agg_lines.append(l)
            l = ""
    if len(l)>0:
        #last line had a trailing backslash... meh
        agg_lines.append(l)
    debug("loaded %s aggregated lines", len(agg_lines))
    #parse name=value pairs:
    for sline in agg_lines:
        if sline.find("=")<=0:
            debug("skipping line which is missing an equal sign: %s", sline)
            continue
        props = sline.split("=", 1)
        assert len(props)==2
        name = props[0].strip()
        value = props[1].strip()
        current_value = d.get(name)
        if current_value:
            if type(current_value)==list:
                d[name] = current_value + [value]
            else:
                d[name] = [current_value, value]
            debug("added to: %s='%s'", name, d[name])
        else:
            debug("assigned (new): %s='%s'", name, value)
            d[name] = value
    return  d


def conf_files(conf_dir, xpra_conf_filename=DEFAULT_XPRA_CONF_FILENAME):
    """
        Returns all the config file paths found in the config directory
        ie: ["/etc/xpra/conf.d/15_features.conf", ..., "/etc/xpra/xpra.conf"]
    """
    d = []
    cdir = os.path.expanduser(conf_dir)
    if not os.path.exists(cdir) or not os.path.isdir(cdir):
        debug("invalid config directory: %s", cdir)
        return d
    #look for conf.d subdirectory:
    conf_d_dir = os.path.join(cdir, "conf.d")
    if os.path.exists(conf_d_dir) and os.path.isdir(conf_d_dir):
        for f in sorted(os.listdir(conf_d_dir)):
            if f.endswith(".conf"):
                conf_file = os.path.join(conf_d_dir, f)
                if os.path.isfile(conf_file):
                    d.append(conf_file)
    conf_file = os.path.join(cdir, xpra_conf_filename)
    if not os.path.exists(conf_file) or not os.path.isfile(conf_file):
        debug("config file does not exist: %s", conf_file)
    else:
        d.append(conf_file)
    return d

def read_xpra_conf(conf_dir, xpra_conf_filename=DEFAULT_XPRA_CONF_FILENAME):
    """
        Reads an <xpra_conf_filename> file from the given directory,
        returns a dict with values as strings and arrays of strings.
    """
    files = conf_files(conf_dir, xpra_conf_filename)
    debug("read_xpra_conf(%s,%s) conf files: %s" % (conf_dir, xpra_conf_filename, files))
    d = {}
    for f in files:
        cd = read_config(f)
        debug("config(%s)=%s" % (f, cd))
        d.update(cd)
    return d

def read_xpra_defaults():
    """
        Reads the global <xpra_conf_filename> from the <conf_dir>
        and then the user-specific one.
        (the latter overrides values from the former)
        returns a dict with values as strings and arrays of strings.
        If the <conf_dir> is not specified, we figure out its location.
    """
    from xpra.platform.paths import get_default_conf_dirs, get_system_conf_dirs, get_user_conf_dirs
    # load config files in this order (the later ones override earlier ones):
    # * application defaults   (ie: "/Volumes/Xpra/Xpra.app/Contents/Resources/" on OSX)
    #                          (ie: "C:\Program Files\Xpra\" on win32)
    #                          (ie: None on others)
    # * system defaults        (ie: "/etc/xpra" on Posix - not on OSX)
    #                          (ie: "/Library/Application Support/Xpra" on OSX)
    #                          (ie: "C:\Documents and Settings\All Users\Application Data\Xpra" with XP)
    #                          (ie: "C:\ProgramData\Xpra" with Vista onwards)
    # * user config            (ie: "~/.xpra/" on all Posix, including OSX)
    #                          (ie: "C:\Documents and Settings\Username\Application Data\Xpra" with XP)
    #                          (ie: "C:\Users\<user name>\AppData\Roaming" with Visa onwards)
    dirs = get_default_conf_dirs() + get_system_conf_dirs() + get_user_conf_dirs()
    defaults = {}
    for d in dirs:
        if not d:
            continue
        ad = os.path.expanduser(d)
        if not os.path.exists(ad):
            debug("read_xpra_defaults: skipping %s", ad)
            continue
        defaults.update(read_xpra_conf(ad))
        debug("read_xpra_defaults: updated defaults with %s", ad)
    may_create_user_config()
    return defaults

def may_create_user_config(xpra_conf_filename=DEFAULT_XPRA_CONF_FILENAME):
    from xpra.platform.paths import get_user_conf_dirs
    #save a user config template:
    udirs = get_user_conf_dirs()
    if udirs:
        has_user_conf = None
        for d in udirs:
            if conf_files(d):
                has_user_conf = d
                break
        if not has_user_conf:
            debug("no user configuration file found, trying to create one")
            for d in udirs:
                ad = os.path.expanduser(d)
                conf_file = os.path.join(ad, xpra_conf_filename)
                try:
                    if not os.path.exists(ad):
                        os.makedirs(ad, int('700', 8))
                    with open(conf_file, 'w') as f:
                        f.write("# xpra user configuration file\n")
                        f.write("# place your custom settings in this file\n")
                        f.write("# they will take precedence over the system default ones.\n")
                        f.write("\n")
                        f.write("# Examples:\n")
                        f.write("# speaker=off\n")
                        f.write("# dpi=144\n")
                        f.write("\n")
                        f.write("# For more information on the file format,\n")
                        f.write("# see the xpra manual at:\n")
                        f.write("# https://xpra.org/manual.html\n")
                        f.write("\n")
                        f.flush()
                    debug("created default config in "+d)
                    break
                except Exception as e:
                    debug("failed to create default config in '%s': %s" % (conf_file, e))


OPTIONS_VALIDATION = {}

OPTION_TYPES = {
                    #string options:
                    "encoding"          : str,
                    "title"             : str,
                    "username"          : str,
                    "password"          : str,
                    "auth"              : str,
                    "vsock-auth"        : str,
                    "tcp-auth"          : str,
                    "ssl-auth"          : str,
                    "wm-name"           : str,
                    "session-name"      : str,
                    "dock-icon"         : str,
                    "tray-icon"         : str,
                    "window-icon"       : str,
                    "password-file"     : str,
                    "keyboard-raw"      : bool,
                    "keyboard-layout"   : str,
                    "keyboard-layouts"  : list,
                    "keyboard-variant"  : str,
                    "keyboard-variants" : list,
                    "keyboard-options"  : str,
                    "clipboard"         : str,
                    "clipboard-direction" : str,
                    "clipboard-filter-file" : str,
                    "remote-clipboard"  : str,
                    "local-clipboard"   : str,
                    "pulseaudio-command": str,
                    "tcp-encryption"    : str,
                    "tcp-encryption-keyfile": str,
                    "encryption"        : str,
                    "encryption-keyfile": str,
                    "pidfile"           : str,
                    "mode"              : str,
                    "ssh"               : str,
                    "systemd-run"       : str,
                    "systemd-run-args"  : str,
                    "xvfb"              : str,
                    "socket-dir"        : str,
                    "mmap"              : str,
                    "log-dir"           : str,
                    "log-file"          : str,
                    "border"            : str,
                    "window-close"      : str,
                    "max-size"          : str,
                    "desktop-scaling"   : str,
                    "display"           : str,
                    "tcp-proxy"         : str,
                    "download-path"     : str,
                    "open-command"      : str,
                    "remote-logging"    : str,
                    "lpadmin"           : str,
                    "lpinfo"            : str,
                    "add-printer-options" : list,
                    "pdf-printer"       : str,
                    "postscript-printer": str,
                    "debug"             : str,
                    "input-method"      : str,
                    "microphone"        : str,
                    "speaker"           : str,
                    "sound-source"      : str,
                    "html"              : str,
                    "socket-permissions": str,
                    "exec-wrapper"      : str,
                    "dbus-launch"       : str,
                    "webcam"            : str,
                    #ssl options:
                    "ssl"               : str,
                    "ssl-key"           : str,
                    "ssl-cert"          : str,
                    "ssl-protocol"      : str,
                    "ssl-ca-certs"      : str,
                    "ssl-ca-data"       : str,
                    "ssl-ciphers"       : str,
                    "ssl-client-verify-mode"   : str,
                    "ssl-server-verify-mode"   : str,
                    "ssl-verify-flags"  : str,
                    "ssl-check-hostname": bool,
                    "ssl-server-hostname" : str,
                    "ssl-options"       : str,
                    #int options:
                    "quality"           : int,
                    "min-quality"       : int,
                    "speed"             : int,
                    "min-speed"         : int,
                    "compression_level" : int,
                    "dpi"               : int,
                    "video-scaling"     : int,
                    "file-size-limit"   : int,
                    "idle-timeout"      : int,
                    "server-idle-timeout" : int,
                    "sync-xvfb"         : int,
                    #float options:
                    "auto-refresh-delay": float,
                    #boolean options:
                    "daemon"            : bool,
                    "use-display"       : bool,
                    "fake-xinerama"     : bool,
                    "resize_display"    : bool,
                    "tray"              : bool,
                    "pulseaudio"        : bool,
                    "dbus-proxy"        : bool,
                    "mmap-group"        : bool,
                    "readonly"          : bool,
                    "keyboard-sync"     : bool,
                    "pings"             : bool,
                    "cursors"           : bool,
                    "bell"              : bool,
                    "notifications"     : bool,
                    "xsettings"         : bool,
                    "system-tray"       : bool,
                    "sharing"           : bool,
                    "delay-tray"        : bool,
                    "windows"           : bool,
                    "exit-with-children": bool,
                    "exit-with-client"  : bool,
                    "exit-ssh"          : bool,
                    "dbus-control"      : bool,
                    "av-sync"           : bool,
                    "opengl"            : bool,
                    "mdns"              : bool,
                    "file-transfer"     : bool,
                    "printing"          : bool,
                    "open-files"        : bool,
                    "swap-keys"         : bool,
                    "start-new-commands": bool,
                    "proxy-start-sessions": bool,
                    "desktop-fullscreen": bool,
                    "global-menus"      : bool,
                    #arrays of strings:
                    "pulseaudio-configure-commands" : list,
                    "socket-dirs"       : list,
                    "remote-xpra"       : list,
                    "encodings"         : list,
                    "proxy-video-encoders" : list,
                    "video-encoders"    : list,
                    "csc-modules"       : list,
                    "video-decoders"    : list,
                    "speaker-codec"     : list,
                    "microphone-codec"  : list,
                    "compressors"       : list,
                    "packet-encoders"   : list,
                    "key-shortcut"      : list,
                    "start"             : list,
                    "start-child"       : list,
                    "start-after-connect"       : list,
                    "start-child-after-connect" : list,
                    "start-on-connect"          : list,
                    "start-child-on-connect"    : list,
                    "bind"              : list,
                    "bind-vsock"        : list,
                    "bind-tcp"          : list,
                    "bind-ssl"          : list,
                    "start-env"         : list,
                    "env"               : list,
               }

def get_default_key_shortcuts():
    return [shortcut for e,shortcut in [
               (True,   "Control+Menu:toggle_keyboard_grab"),
               (True,   "Shift+Menu:toggle_pointer_grab"),
               (True,   "Shift+F11:toggle_fullscreen"),
               (True,   "Meta+Shift+F1:show_menu"),
               (True,   "Meta+Shift+F2:show_start_new_command"),
               (True,   "Meta+Shift+F3:show_bug_report"),
               (True,   "Meta+Shift+F4:quit"),
               (True,   "Meta+Shift+F5:increase_quality"),
               (True,   "Meta+Shift+F6:decrease_quality"),
               (True,   "Meta+Shift+F7:increase_speed"),
               (True,   "Meta+Shift+F8:decrease_speed"),
               (True,   "Meta+Shift+F10:magic_key"),
               (True,   "Meta+Shift+F11:show_session_info"),
               (True,   "Meta+Shift+F12:toggle_debug"),
               (True,   "Meta+Shift+plus:scaleup"),
               (OSX,    "Meta+Shift+plusminus:scaleup"),
               (True,   "Meta+Shift+minus:scaledown"),
               (True,   "Meta+Shift+underscore:scaledown"),
               (OSX,    "Meta+Shift+emdash:scaledown"),
               (True,   "Meta+Shift+KP_Add:scaleup"),
               (True,   "Meta+Shift+KP_Subtract:scaledown"),
               (True,   "Meta+Shift+KP_Multiply:scalereset"),
               (True,   "Meta+Shift+bar:scalereset"),
               (True,   "Meta+Shift+question:scalingoff"),
               (OSX,    "Meta+Shift+degree:scalereset")]
                 if e]

def get_default_systemd_run():
    #don't use systemd-run on CentOS / RedHat
    #(it causes failures with "Failed to create bus connection: No such file or directory")
    from xpra.os_util import load_binary_file, strtobytes
    data = strtobytes(load_binary_file("/etc/redhat-release") or "")
    if data and (data.find(b"RedHat")>=0 or data.find(b"CentOS")>=0):
        return "no"
    if data and data.find(b"Fedora")>=0:
        #systemd-run is broken in Fedora 26:
        #https://github.com/systemd/systemd/issues/3388
        try:
            from xpra.os_util import get_linux_distribution
            ld = get_linux_distribution()
            if int(ld[1])>=26:
                return "no"
        except:
            pass
    return "auto"


GLOBAL_DEFAULTS = None
#lowest common denominator here
#(the xpra.conf file shipped is generally better tuned than this - especially for 'xvfb')
def get_defaults():
    global GLOBAL_DEFAULTS
    if GLOBAL_DEFAULTS is not None:
        return GLOBAL_DEFAULTS
    from xpra.platform.features import DEFAULT_SSH_COMMAND, OPEN_COMMAND, DEFAULT_PULSEAUDIO_CONFIGURE_COMMANDS, DEFAULT_PULSEAUDIO_COMMAND, \
                                        DEFAULT_ENV, CAN_DAEMONIZE
    from xpra.platform.paths import get_download_dir, get_remote_run_xpra_scripts
    try:
        from xpra.platform.info import get_username
        username = get_username()
    except:
        username = ""
    conf_dirs = [os.environ.get("XPRA_CONF_DIR")]
    build_root = os.environ.get("RPM_BUILD_ROOT")
    if build_root:
        conf_dirs.append(os.path.join(build_root, "etc", "xpra"))
    xpra_cmd = sys.argv[0]
    bin_dir = None
    if len(sys.argv)>0:
        for strip in ("/usr/bin", "/bin"):
            pos = xpra_cmd.find(strip)
            if pos>=0:
                bin_dir = xpra_cmd[:pos+len(strip)]
                root = xpra_cmd[:pos] or "/"
                conf_dirs.append(os.path.join(root, "etc", "xpra"))
                break
    if sys.prefix=="/usr":
        conf_dirs.append("/etc/xpra")
    else:
        conf_dirs.append(os.path.join(sys.prefix, "etc", "xpra"))
    for conf_dir in [x for x in conf_dirs if x]:
        if os.path.exists(conf_dir):
            break
    xvfb = detect_xvfb_command(conf_dir, bin_dir)
    def addtrailingslash(v):
        if v.endswith("/"):
            return v
        return v+"/"
    if WIN32:
        bind_dirs = ["Main"]
    else:
        bind_dirs = ["auto"]

    ssl_protocol = "TLSv1_2"
    if sys.version_info<(2, 7, 9):
        ssl_protocol = "SSLv23"

    GLOBAL_DEFAULTS = {
                    "encoding"          : "",
                    "title"             : "@title@ on @client-machine@",
                    "username"          : username,
                    "password"          : "",
                    "auth"              : "",
                    "vsock-auth"        : "",
                    "tcp-auth"          : "",
                    "ssl-auth"          : "",
                    "wm-name"           : DEFAULT_NET_WM_NAME,
                    "session-name"      : "",
                    "dock-icon"         : "",
                    "tray-icon"         : "",
                    "window-icon"       : "",
                    "password-file"     : "",
                    "keyboard-raw"      : False,
                    "keyboard-layout"   : "",
                    "keyboard-layouts"  : [],
                    "keyboard-variant"  : "",
                    "keyboard-variants" : [],
                    "keyboard-options"  : "",
                    "clipboard"         : "yes",
                    "clipboard-direction" : "both",
                    "clipboard-filter-file" : "",
                    "remote-clipboard"  : "CLIPBOARD",
                    "local-clipboard"   : "CLIPBOARD",
                    "pulseaudio-command": " ".join(DEFAULT_PULSEAUDIO_COMMAND),
                    "encryption"        : "",
                    "tcp-encryption"    : "",
                    "encryption-keyfile": "",
                    "tcp-encryption-keyfile": "",
                    "pidfile"           : "",
                    "ssh"               : DEFAULT_SSH_COMMAND,
                    "systemd-run"       : get_default_systemd_run(),
                    "systemd-run-args"  : "",
                    "xvfb"              : " ".join(xvfb),
                    "socket-dir"        : "",
                    "log-dir"           : "auto",
                    "log-file"          : "$DISPLAY.log",
                    "border"            : "auto,5:off",
                    "window-close"      : "auto",
                    "max-size"          : "",
                    "desktop-scaling"   : "auto",
                    "display"           : "",
                    "tcp-proxy"         : "",
                    "download-path"     : get_download_dir(),
                    "open-command"      : OPEN_COMMAND,
                    "remote-logging"    : "both",
                    "lpadmin"           : "/usr/sbin/lpadmin",
                    "lpinfo"            : "/usr/sbin/lpinfo",
                    "add-printer-options" : ["-E", "-o printer-is-shared=false", "-u allow:$USER"],
                    "pdf-printer"       : "",
                    "postscript-printer": DEFAULT_POSTSCRIPT_PRINTER,
                    "debug"             : "",
                    "input-method"      : "none",
                    "sound-source"      : "",
                    "html"              : "auto",
                    "socket-permissions": "600",
                    "exec-wrapper"      : "",
                    "dbus-launch"       : "dbus-launch --close-stderr",
                    "webcam"            : ["auto", "no"][OSX],
                    #ssl options:
                    "ssl"               : "auto",
                    "ssl-key"           : "",
                    "ssl-cert"          : "",
                    "ssl-protocol"      : ssl_protocol,
                    "ssl-ca-certs"      : "default",
                    "ssl-ca-data"       : "",
                    "ssl-ciphers"       : "DEFAULT",
                    "ssl-client-verify-mode"   : "optional",
                    "ssl-server-verify-mode"   : "required",
                    "ssl-verify-flags"  : "X509_STRICT",
                    "ssl-check-hostname": False,
                    "ssl-server-hostname": "localhost",
                    "ssl-options"       : "ALL,NO_COMPRESSION",
                    "quality"           : 0,
                    "min-quality"       : 30,
                    "speed"             : 0,
                    "min-speed"         : 30,
                    "compression_level" : 1,
                    "dpi"               : 0,
                    "video-scaling"     : 1,
                    "file-size-limit"   : 100,
                    "idle-timeout"      : 0,
                    "server-idle-timeout" : 0,
                    "sync-xvfb"         : 0,
                    "auto-refresh-delay": 0.15,
                    "daemon"            : CAN_DAEMONIZE,
                    "use-display"       : False,
                    "fake-xinerama"     : not OSX and not WIN32,
                    "resize-display"    : not OSX and not WIN32,
                    "tray"              : True,
                    "pulseaudio"        : not OSX and not WIN32,
                    "dbus-proxy"        : not OSX and not WIN32,
                    "mmap"              : ["no", "yes"][not OSX and not WIN32],
                    "mmap-group"        : False,
                    "speaker"           : ["disabled", "on"][has_sound_support()],
                    "microphone"        : ["disabled", "off"][has_sound_support()],
                    "readonly"          : False,
                    "keyboard-sync"     : True,
                    "pings"             : False,
                    "cursors"           : True,
                    "bell"              : True,
                    "notifications"     : True,
                    "xsettings"         : not OSX and not WIN32,
                    "system-tray"       : True,
                    "sharing"           : False,
                    "delay-tray"        : False,
                    "windows"           : True,
                    "exit-with-children": False,
                    "exit-with-client"  : False,
                    "start-after-connect": False,
                    "start-new-commands": False,
                    "proxy-start-sessions": True,
                    "av-sync"           : True,
                    "exit-ssh"          : True,
                    "dbus-control"      : not WIN32 and not OSX,
                    "opengl"            : get_opengl_default(),
                    "mdns"              : not WIN32,
                    "file-transfer"     : True,
                    "printing"          : True,
                    "open-files"        : False,
                    "swap-keys"         : OSX,  #only used on osx
                    "desktop-fullscreen": False,
                    "global-menus"      : True,
                    "pulseaudio-configure-commands"  : [" ".join(x) for x in DEFAULT_PULSEAUDIO_CONFIGURE_COMMANDS],
                    "socket-dirs"       : [],
                    "remote-xpra"       : get_remote_run_xpra_scripts(),
                    "encodings"         : ["all"],
                    "proxy-video-encoders" : [],
                    "video-encoders"    : ["all"],
                    "csc-modules"       : ["all"],
                    "video-decoders"    : ["all"],
                    "speaker-codec"     : [],
                    "microphone-codec"  : [],
                    "compressors"       : ["all"],
                    "packet-encoders"   : ["all"],
                    "key-shortcut"      : get_default_key_shortcuts(),
                    "bind"              : bind_dirs,
                    "bind-vsock"        : [],
                    "bind-tcp"          : [],
                    "bind-ssl"          : [],
                    "start"             : [],
                    "start-child"       : [],
                    "start-after-connect"       : [],
                    "start-child-after-connect" : [],
                    "start-on-connect"          : [],
                    "start-child-on-connect"    : [],
                    "start-env"         : DEFAULT_ENV,
                    "env"               : [],
                    }
    return GLOBAL_DEFAULTS
#fields that got renamed:
CLONES = {}

#these options should not be specified in config files:
NO_FILE_OPTIONS = ["daemon"]


TRUE_OPTIONS = ["yes", "true", "1", "on", True]
FALSE_OPTIONS = ["no", "false", "0", "off", False]
def parse_bool(k, v):
    if type(v)==str:
        v = v.lower()
    if v in TRUE_OPTIONS:
        return True
    elif v in FALSE_OPTIONS:
        return False
    elif v in ["auto", None]:
        #keep default - which may be None!
        return None
    else:
        try:
            return bool(int(v))
        except:
            warn("Warning: cannot parse value '%s' for '%s' as a boolean" % (v, k))
            return None

def print_bool(k, v, true_str='yes', false_str='no'):
    if type(v)==type(None):
        return 'auto'
    if type(v)==bool:
        if v:
            return true_str
        return false_str
    warn("Warning: cannot print value '%s' for '%s' as a boolean" % (v, k))

def parse_bool_or_int(k, v):
    return parse_bool_or_number(int, k, v)

def parse_bool_or_number(numtype, k, v, auto=0):
    if type(v)==str:
        v = v.lower()
    if v in TRUE_OPTIONS:
        return 1
    elif v in FALSE_OPTIONS:
        return 0
    else:
        return parse_number(numtype, k, v, auto)

def parse_number(numtype, k, v, auto=0):
    if type(v)==str:
        v = v.lower()
    if v=="auto":
        return auto
    try:
        return numtype(v)
    except Exception as e:
        warn("Warning: cannot parse value '%s' for '%s' as a type %s: %s" % (v, k, numtype, e))
        return None

def print_number(i, auto_value=0):
    if i==auto_value:
        return "auto"
    return str(i)

def validate_config(d={}, discard=NO_FILE_OPTIONS, extras_types={}, extras_validation={}):
    """
        Validates all the options given in a dict with fields as keys and
        strings or arrays of strings as values.
        Each option is strongly typed and invalid value are discarded.
        We get the required datatype from OPTION_TYPES
    """
    validations = OPTIONS_VALIDATION.copy()
    validations.update(extras_validation)
    option_types = OPTION_TYPES.copy()
    option_types.update(extras_types)
    nd = {}
    for k, v in d.items():
        if k in discard:
            warn("Warning: option '%s' is not allowed in configuration files" % k)
            continue
        vt = option_types.get(k)
        if vt is None:
            warn("Warning: invalid option: '%s'" % k)
            continue
        if vt==str:
            if type(v)!=str:
                warn("invalid value for '%s': %s (string required)" % (k, type(v)))
                continue
        elif vt==int:
            v = parse_bool_or_number(int, k, v)
            if v==None:
                continue
        elif vt==float:
            v = parse_number(float, k, v)
            if v==None:
                continue
        elif vt==bool:
            v = parse_bool(k, v)
            if v is None:
                continue
        elif vt==list:
            if type(v)==str:
                #could just be that we specified it only once..
                v = [v]
            elif type(v)==list or v==None:
                #ok so far..
                pass
            else:
                warn("Warning: invalid value for '%s': %s (a string or list of strings is required)" % (k, type(v)))
                continue
        else:
            warn("Error: unknown option type for '%s': %s" % (k, vt))
        validation = validations.get(k)
        if validation and v is not None:
            msg = validation(v)
            if msg:
                warn("Warning: invalid value for '%s': %s, %s" % (k, v, msg))
                continue
        nd[k] = v
    return nd


def make_defaults_struct(extras_defaults={}, extras_types={}, extras_validation={}):
    #populate config with default values:
    defaults = read_xpra_defaults()
    return dict_to_validated_config(defaults, extras_defaults, extras_types, extras_validation)

def dict_to_validated_config(d={}, extras_defaults={}, extras_types={}, extras_validation={}):
    options = get_defaults().copy()
    options.update(extras_defaults)
    #parse config:
    validated = validate_config(d, extras_types=extras_types, extras_validation=extras_validation)
    options.update(validated)
    for k,v in CLONES.items():
        if k in options:
            options[v] = options[k]
    config = AdHocStruct()
    for k,v in options.items():
        setattr(config, name_to_field(k), v)
    return config


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
        return ",".join(str(x).lower().strip() for x in value if x)
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
    pvestr  = _csvstr(options.proxy_video_encoders)
    def getlist(strarg, help_txt, all_list):
        if strarg=="help":
            raise InitInfo("the following %s may be available: %s" % (help_txt, ", ".join(all_list)))
        elif strarg=="none":
            return []
        elif strarg=="all":
            return all_list
        else:
            return [x for x in _nodupes(strarg) if x]
    options.video_encoders  = getlist(vestr,    "video encoders",   aveco)
    options.csc_modules     = getlist(cscstr,   "csc modules",      acsco)
    options.video_decoders  = getlist(vdstr,    "video decoders",   avedo)
    options.proxy_video_encoders = getlist(pvestr, "proxy video encoders", aveco)

def fixup_socketdirs(options, defaults):
    if not options.socket_dirs:
        from xpra.platform.paths import get_socket_dirs
        options.socket_dirs = getattr(defaults, "socket_dirs", get_socket_dirs())
    elif type(options.socket_dirs)==str:
        options.socket_dirs = options.socket_dirs.split(os.path.pathsep)
    else:
        assert type(options.socket_dirs) in (list, tuple)
        options.socket_dirs = [v for x in options.socket_dirs for v in x.split(os.path.pathsep)]

def fixup_encodings(options):
    from xpra.codecs.loader import PREFERED_ENCODING_ORDER
    RENAME = {"jpg" : "jpeg"}
    if options.encoding:
        options.encoding = RENAME.get(options.encoding, options.encoding)
    estr = _csvstr(options.encodings)
    if estr=="all":
        #replace with an actual list
        options.encodings = PREFERED_ENCODING_ORDER
        return
    encodings = [RENAME.get(x, x) for x in _nodupes(estr)]
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
        compressors = compression.PERFORMANCE_ORDER
    else:
        compressors = _nodupes(cstr)
        unknown = [x for x in compressors if x and x not in compression.ALL_COMPRESSORS]
        if unknown:
            warn("warning: invalid compressor(s) specified: %s" % (", ".join(unknown)))
    options.compressors = compressors

def fixup_packetencoding(options):
    #packet encoding
    from xpra.net import packet_encoding
    pestr = _csvstr(options.packet_encoders)
    if pestr=="all":
        packet_encoders = packet_encoding.PERFORMANCE_ORDER
    else:
        packet_encoders = _nodupes(pestr)
        unknown = [x for x in packet_encoders if x and x not in packet_encoding.ALL_ENCODERS]
        if unknown:
            warn("warning: invalid packet encoder(s) specified: %s" % (", ".join(unknown)))
    options.packet_encoders = packet_encoders

def fixup_keyboard(options):
    #variants and layouts can be specified as CSV, convert them to lists:
    def p(v):
        try:
            from xpra.util import remove_dupes
            r = remove_dupes([x.strip() for x in v.split(",")])
            #remove empty string if that's the only value:
            if r and len(r)==1 and r[0]=="":
                r = []
            return r
        except:
            return []
    options.keyboard_layouts = p(options.keyboard_layouts)
    options.keyboard_variants = p(options.keyboard_variants)
    options.keyboard_raw = parse_bool("keyboard-raw", options.keyboard_raw)

def fixup_clipboard(options):
    cd = options.clipboard_direction.lower().replace("-", "")
    if cd=="toserver":
        options.clipboard_direction = "to-server"
    elif cd=="toclient":
        options.clipboard_direction = "to-client"
    elif cd=="both":
        options.clipboard_direction = "both"
    elif cd=="disabled" or cd=="none":
        options.clipboard_direction = "disabled"
    else:
        warn("Warning: invalid value for clipboard-direction: '%s'" % options.clipboard_direction)
        warn(" specify 'to-server', 'to-client' or 'both'")
        options.clipboard_direction = "disabled"

def fixup_bool(options):
    options.sharing = parse_bool("sharing", options.sharing) or False

def abs_paths(options):
    #convert to absolute paths before we daemonize
    for k in ("clipboard-filter-file",
              "tcp-encryption-keyfile", "encryption-keyfile",
              "log-dir",
              "download-path", "exec-wrapper",
              "ssl-key", "ssl-cert", "ssl-ca-certs"):
        f = k.replace("-", "_")
        v = getattr(options, f)
        if v and (k!="ssl-ca-certs" or v!="default"):
            if os.path.isabs(v) or v=="auto":
                continue
            if v.startswith("~") or v.startswith("$"):
                continue
            setattr(options, f, os.path.abspath(v))

def fixup_options(options, defaults={}):
    fixup_encodings(options)
    fixup_compression(options)
    fixup_packetencoding(options)
    fixup_video_all_or_none(options)
    fixup_socketdirs(options, defaults)
    fixup_clipboard(options)
    fixup_keyboard(options)
    fixup_bool(options)
    abs_paths(options)
    #remote-xpra is meant to be a list, but the user can specify a string using the command line,
    #in which case we replace all the default values with this single entry:
    if not isinstance(options.remote_xpra, (list, tuple)):
        options.remote_xpra = [options.remote_xpra]


def main():
    from xpra.util import nonl
    def print_options(o):
        for k,ot in sorted(OPTION_TYPES.items()):
            v = getattr(o, name_to_field(k), "")
            if ot==bool and v is None:
                v = "Auto"
            if type(v)==list:
                v = ", ".join(str(x) for x in v)
            print("* %-32s : %s" % (k, nonl(v)))
    from xpra.platform import program_context
    from xpra.log import enable_color
    with program_context("Config-Info", "Config Info"):
        enable_color()
        args = list(sys.argv[1:])
        if "-v" in args or "--verbose" in sys.argv:
            global debug
            def debug(*args):
                print(args[0] % args[1:])
            args.remove("-v")

        print("Default Configuration:")
        print_options(make_defaults_struct())
        if len(args)>0:
            for filename in args:
                print("")
                print("Configuration file '%s':" % filename)
                if not os.path.exists(filename):
                    print(" Error: file not found")
                    continue
                d = read_config(filename)
                config = dict_to_validated_config(d)
                print_options(config)


if __name__ == "__main__":
    main()
