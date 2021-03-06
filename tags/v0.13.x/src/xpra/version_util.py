# This file is part of Xpra.
# Copyright (C) 2011-2014 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

#tricky: use xpra.scripts.config to get to the python "platform" module
from xpra.scripts.config import python_platform
import sys
from xpra import __version__ as local_version
from xpra.log import Logger
log = Logger("util")

def version_as_numbers(version):
    return [int(x) for x in version.split(".")]

def version_compat_check(remote_version):
    if remote_version is None:
        msg = "remote version not available!"
        log(msg)
        return msg
    rv = version_as_numbers(remote_version)
    lv = version_as_numbers(local_version)
    if rv==lv:
        log("identical remote version: %s", remote_version)
        return None
    if rv[:2]<=[0, 2]:
        #0.3 is the oldest version we support
        msg = "remote version %s is too old, sorry" % str(rv[:2])
        log(msg)
        return  msg
    if rv[0:3]<=[0, 7, 8]:
        log("WARNING: the remote version %s is old and broken, upgrade to the latest stable version", remote_version)
        return None
    if rv[0]>0:
        log("newer remote version %s may work, we'll see..", remote_version)
        return  None
    log("local version %s should be compatible with remote version: %s", local_version, remote_version)
    return None

def mk(*parts):
    #make a prefix from a list of parts
    #(dot seperated values)
    return ".".join([str(x) for x in parts if x])

def get_host_info(prefix=""):
    #this function is for non UI thread info
    info = {}
    import os
    try:
        import socket
        for k,v in {
                    "pid"                   : os.getpid(),
                    "byteorder"             : sys.byteorder,
                    "hostname"              : socket.gethostname(),
                    "python.full_version"   : sys.version,
                    "python.version"        : sys.version_info[:3],
                    }.items():
            info[mk(prefix, k)] = v
    except:
        pass
    for x in ("uid", "gid"):
        if hasattr(os, "get%s" % x):
            try:
                info[mk(prefix, x)] = getattr(os, "get%s" % x)()
            except:
                pass
    return info

def get_version_info(prefix=""):
    props = {
             mk(prefix, "version") : local_version
             }
    try:
        from xpra.src_info import LOCAL_MODIFICATIONS, REVISION
        from xpra.build_info import BUILD_DATE, BUILT_BY, BUILT_ON, BUILD_BIT, BUILD_CPU, \
                                    COMPILER_VERSION, LINKER_VERSION, BUILD_TIME, PYTHON_VERSION, CYTHON_VERSION
        for k,v in {
                    "local_modifications"  : LOCAL_MODIFICATIONS,
                    "date"                 : BUILD_DATE,
                    "time"                 : BUILD_TIME,
                    "by"                   : BUILT_BY,
                    "on"                   : BUILT_ON,
                    "bit"                  : BUILD_BIT,
                    "cpu"                  : BUILD_CPU,
                    "revision"             : REVISION,
                    "compiler"             : COMPILER_VERSION,
                    "linker"               : LINKER_VERSION,
                    "python"               : PYTHON_VERSION,
                    "cython"               : CYTHON_VERSION,
                  }.items():
            props[mk(prefix, k)] = v
    except:
        pass
    return props

def do_get_platform_info():
    from xpra.os_util import platform_name
    info = {
            ""          : sys.platform,
            "name"      : platform_name(sys.platform, python_platform.release()),
            "release"   : python_platform.release(),
            "platform"  : python_platform.platform(),
            "machine"   : python_platform.machine(),
            "processor" : python_platform.processor(),
            }
    if sys.platform.startswith("linux") and hasattr(python_platform, "linux_distribution"):
        info["linux_distribution"] = python_platform.linux_distribution()
    return info
#cache the output:
platform_info_cache = None
def get_platform_info_cache():
    global platform_info_cache
    if platform_info_cache is None:
        platform_info_cache = do_get_platform_info()
    return platform_info_cache


def get_platform_info(prefix=""):
    info = {}
    for k,v in get_platform_info_cache().items():
        info[mk(prefix, k)] = v
    return info
