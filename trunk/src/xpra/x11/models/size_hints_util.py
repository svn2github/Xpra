# This file is part of Xpra.
# Copyright (C) 2008, 2009 Nathaniel Smith <njs@pobox.com>
# Copyright (C) 2011-2015 Antoine Martin <antoine@xpra.org>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.


from xpra.x11.common import MAX_WINDOW_SIZE
MAX_ASPECT = 2**15-1

from xpra.log import Logger
log = Logger("x11", "window")


def sanitize_size_hints(size_hints):
    """
        Some applications may set nonsensical values,
        try our best to come up with something that can actually be used.
    """
    if size_hints is None:
        return
    for attr in ("min-aspect", "max-aspect"):
        v = size_hints.get(attr)
        if v is not None:
            try:
                f = float(v)
            except:
                f = None
            if f is None or f<=0 or f>=MAX_ASPECT:
                log.warn("Warning: clearing invalid aspect hint value for %s: %s", attr, v)
                del size_hints[attr]
    for attr in ("minimum-aspect-ratio", "maximum-aspect-ratio"):
        v = size_hints.get(attr)
        if v is not None:
            try:
                f = float(v[0])/float(v[1])
            except:
                f = None
            if f is None or f<=0 or f>=MAX_ASPECT:
                log.warn("Warning: clearing invalid aspect hint value for %s: %s", attr, v)
                del size_hints[attr]
    for attr in ("maximum-size", "minimum-size", "base-size", "increment"):
        v = size_hints.get(attr)
        if v is not None:
            try:
                w,h = v
            except:
                w,h = None,None
            if (w is None or h is None) or w>=MAX_WINDOW_SIZE or h>=MAX_WINDOW_SIZE:
                log("clearing invalid size hint value for %s: %s", attr, v)
                del size_hints[attr]
    for attr in ("minimum-aspect-ratio", "maximum-aspect-ratio"):
        v = size_hints.get(attr)
        if v is not None:
            try:
                w,h = v
            except:
                w,h = None,None
            if (w is None or w==0 or h is None or h==0) or w>=MAX_WINDOW_SIZE or h>=MAX_WINDOW_SIZE:
                log.warn("Warning: clearing invalid size hint value for %s: %s", attr, v)
                del size_hints[attr]
    #if max-size is smaller than min-size (bogus), clamp it..
    mins = size_hints.get("minimum-size")
    maxs = size_hints.get("maximum-size")
    if mins is not None and maxs is not None:
        clamped = False
        minw,minh = mins
        maxw,maxh = maxs
        if minw<0 and minh<0:
            #doesn't do anything
            size_hints["minimum-size"] = None
            clamped = True
        if maxw<=0 or maxh<=0:
            #doesn't make sense!
            size_hints["maximum-size"] = None
            clamped = True
        if not clamped:
            if minw>0 and minw>maxw:
                #min higher than max!
                if minw<=256:
                    maxw = minw
                elif maxw>=256:
                    minw = maxw
                else:
                    minw = maxw = 256
                clamped = True
            if minh>0 and minh>maxh:
                #min higher than max!
                if minh<=256:
                    maxh = minh
                elif maxh>=256:
                    minh = maxh
                else:
                    minh = maxh = 256
                clamped = True
            if clamped:
                size_hints["minimum-size"] = minw, minh
                size_hints["maximum-size"] = maxw, maxh
        if clamped:
            log.warn("Warning: invalid min_size=%s / max_size=%s changed to: %s / %s",
                     mins, maxs, size_hints.get("minimum-size"), size_hints.get("maximum-size"))
