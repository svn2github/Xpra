# This file is part of Xpra.
# Copyright (C) 2012 Serviware (Arthur Huillet, <ahuillet@serviware.com>)
# Copyright (C) 2012-2014 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

from xpra.log import Logger
log = Logger("opengl", "window")

from gtk import gdk
import gobject

from xpra.client.gtk2.gtk2_window_base import GTK2WindowBase
from xpra.client.gl.gl_window_backing import GLPixmapBacking


class GLClientWindow(GTK2WindowBase):

    def __init__(self, *args):
        log("GLClientWindow(..)")
        GTK2WindowBase.__init__(self, *args)
        self.add(self._backing._backing)

    def get_backing_class(self):
        return GLPixmapBacking

    def setup_window(self):
        self._client_properties["encoding.uses_swscale"] = False
        GTK2WindowBase.setup_window(self)


    def __str__(self):
        return "GLClientWindow(%s : %s)" % (self._id, self._backing)

    def is_GL(self):
        return True

    def set_alpha(self):
        GTK2WindowBase.set_alpha(self)
        rgb_formats = self._client_properties.get("encodings.rgb_formats", [])
        #gl_window_backing supports BGR(A) too:
        if "RGBA" in rgb_formats:
            rgb_formats.append("BGRA")
        if "RGB" in rgb_formats:
            rgb_formats.append("BGR")
            #TODO: we could handle BGRX as BGRA too...
            #rgb_formats.append("BGRX")

    def spinner(self, ok):
        if not self._backing.paint_screen or not self._backing._backing or not self.can_have_spinner():
            return
        w, h = self.get_size()
        if ok:
            self._backing.gl_expose_event(self._backing._backing, "spinner: fake event")
            self.queue_draw(0, 0, w, h)
        else:
            self._backing.gl_expose_event(self._backing._backing, "spinner: fake event")
            window = self._backing._backing.get_window()
            context = window.cairo_create()
            self.paint_spinner(context, gdk.Rectangle(0, 0, w, h))

    def do_expose_event(self, event):
        log("GL do_expose_event(%s)", event)

    def do_configure_event(self, event):
        log("GL do_configure_event(%s)", event)
        GTK2WindowBase.do_configure_event(self, event)
        self._backing.paint_screen = True

    def destroy(self):
        self._backing.paint_screen = False
        GTK2WindowBase.destroy(self)

    def magic_key(self, *args):
        if self.border:
            self.border.shown = (not self.border.shown)
            self.queue_draw(0, 0, *self._size)

gobject.type_register(GLClientWindow)
