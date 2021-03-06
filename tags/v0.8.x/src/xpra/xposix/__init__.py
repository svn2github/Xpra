# This file is part of Parti.
# Copyright (C) 2010 Nathaniel Smith <njs@pobox.com>
# Parti is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

# Platform-specific code for Posix systems with X11 display.
import os.path

XPRA_LOCAL_SERVERS_SUPPORTED = True
DEFAULT_SSH_CMD = "ssh"
GOT_PASSWORD_PROMPT_SUGGESTION = "Perhaps you need to set up your ssh agent?\n"

def add_client_options(parser):
    from xpra.platform import add_notray_option, add_delaytray_option
    add_notray_option(parser)
    add_delaytray_option(parser)

def get_machine_id():
    v = u""
    for filename in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
        if os.path.exists(filename) and os.path.isfile(filename):
            f = None
            try:
                try:
                    f = open(filename, 'rb', 'utf-8')
                    v = f.read()
                    break
                finally:
                    if f:
                        f.close()
            except:
                pass
    return  v
