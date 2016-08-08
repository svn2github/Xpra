# coding=utf8
# This file is part of Xpra.
# Copyright (C) 2012-2014 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import time
import win32api         #@UnresolvedImport
import win32con         #@UnresolvedImport
import win32ui          #@UnresolvedImport
import win32gui         #@UnresolvedImport
from xpra.log import Logger
log = Logger("shadow", "win32")

from xpra.os_util import StringIOClass
from xpra.server.gtk_server_base import GTKServerBase
from xpra.server.shadow_server_base import ShadowServerBase, RootWindowModel
from xpra.platform.win32.keyboard_config import KeyboardConfig
from xpra.codecs.image_wrapper import ImageWrapper

BUTTON_EVENTS = {
                 #(button,up-or-down)  : win-event-name
                 (1, True)  : (win32con.MOUSEEVENTF_LEFTDOWN,   0),
                 (1, False) : (win32con.MOUSEEVENTF_LEFTUP,     0),
                 (2, True)  : (win32con.MOUSEEVENTF_MIDDLEDOWN, 0),
                 (2, False) : (win32con.MOUSEEVENTF_MIDDLEUP,   0),
                 (3, True)  : (win32con.MOUSEEVENTF_RIGHTDOWN,  0),
                 (3, False) : (win32con.MOUSEEVENTF_RIGHTUP,    0),
                 (4, True)  : (win32con.MOUSEEVENTF_WHEEL,      win32con.WHEEL_DELTA),
                 (5, True)  : (win32con.MOUSEEVENTF_WHEEL,      -win32con.WHEEL_DELTA),
                 }

class Win32RootWindowModel(RootWindowModel):

    def __init__(self, root):
        RootWindowModel.__init__(self, root)
        self.metrics = None
        self.ddc, self.cdc, self.memdc, self.bitmap = None, None, None, None

    def get_root_window_size(self):
        w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        return w, h

    def get_metrics(self):
        dx = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        dy = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        dw = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        dh = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        return dx, dy, dw, dh

    def get_image(self, x, y, width, height, logger=None):
        start = time.time()
        desktop_wnd = win32gui.GetDesktopWindow()
        metrics = self.get_metrics()
        if self.metrics is None or self.metrics!=metrics:
            #new metrics, start from scratch:
            self.metrics = metrics
            self.ddc, self.cdc, self.memdc, self.bitmap = None, None, None, None
        dx, dy, dw, dh = metrics
        #clamp rectangle requested to the virtual desktop size:
        if x<dx:
            width -= x-dx
            x = dx
        if y<dy:
            height -= y-dy
            y = dy
        if width>dw:
            width = dw
        if height>dh:
            height = dh
        try:
            if not self.ddc:
                self.ddc = win32gui.GetWindowDC(desktop_wnd)
                assert self.ddc, "cannot get a drawing context from the desktop window %s" % desktop_wnd
                self.cdc = win32ui.CreateDCFromHandle(self.ddc)
                assert self.cdc, "cannot get a compatible drawing context from the desktop drawing context %s" % self.ddc
                self.memdc = self.cdc.CreateCompatibleDC()
                self.bitmap = win32ui.CreateBitmap()
                self.bitmap.CreateCompatibleBitmap(self.cdc, width, height)
            self.memdc.SelectObject(self.bitmap)
            select_time = time.time()
            log("get_image up to SelectObject took %ims", (select_time-start)*1000)
            self.memdc.BitBlt((0, 0), (width, height), self.cdc, (x, y), win32con.SRCCOPY)
            bitblt_time = time.time()
            log("get_image BitBlt took %ims", (bitblt_time-select_time)*1000)
            pixels = self.bitmap.GetBitmapBits(True)
            log("get_image GetBitmapBits took %ims", (time.time()-bitblt_time)*1000)
        finally:
            pass
        assert pixels, "no pixels returned from GetBitmapBits"
        v = ImageWrapper(x, y, width, height, pixels, "BGRX", 24, width*4, planes=ImageWrapper.PACKED, thread_safe=True)
        if logger==None:
            logger = log
        log("get_image%s=%s took %ims", (x, y, width, height), v, (time.time()-start)*1000)
        return v

    def take_screenshot(self):
        from PIL import Image
        x, y, w, h = self.get_metrics()
        image = self.get_image(x, y, w, h)
        assert image.get_width()==w and image.get_height()==h
        assert image.get_pixel_format()=="BGRX"
        img = Image.frombuffer("RGB", (w, h), image.get_pixels(), "raw", "BGRX", 0, 1)
        out = StringIOClass()
        img.save(out, format="PNG")
        screenshot = (img.width, img.height, "png", img.width*3, out.getvalue())
        out.close()
        return screenshot

class ShadowServer(ShadowServerBase, GTKServerBase):

    def __init__(self):
        import gtk.gdk
        ShadowServerBase.__init__(self, gtk.gdk.get_default_root_window())
        GTKServerBase.__init__(self)
        self.keycodes = {}
        from xpra.net.bytestreams import set_continue_wait
        #on win32, we want to wait just a little while,
        #to prevent servers spinning wildly on non-blocking sockets:
        set_continue_wait(5)

    def makeRootWindowModel(self):
        return Win32RootWindowModel(self.root)

    def _process_mouse_common(self, proto, wid, pointer, modifiers):
        #adjust pointer position for offset in client:
        x, y = pointer
        wx, wy = self.mapped_at[:2]
        rx, ry = x-wx, y-wy
        win32api.SetCursorPos((rx, ry))

    def get_keyboard_config(self, props):
        return KeyboardConfig()

    def fake_key(self, keycode, press):
        if keycode<=0:
            log.warn("no keycode found for %s", keycode)
            return
        #KEYEVENTF_SILENT = 0X4;
        flags = 0   #KEYEVENTF_SILENT
        if press:
            flags |= win32con.KEYEVENTF_KEYUP
        #get the scancode:
        MAPVK_VK_TO_VSC = 0
        scancode = win32api.MapVirtualKey(keycode, MAPVK_VK_TO_VSC)
        #see: http://msdn.microsoft.com/en-us/library/windows/desktop/ms646304(v=vs.85).aspx
        log("fake_key(%s, %s) calling keybd_event(%s, %s, %s, 0)", keycode, press, keycode, scancode, flags)
        win32api.keybd_event(keycode, scancode, flags, 0)

    def _process_button_action(self, proto, packet):
        wid, button, pressed, pointer, modifiers = packet[1:6]
        self._process_mouse_common(proto, wid, pointer, modifiers)
        self._server_sources.get(proto).user_event()
        event = BUTTON_EVENTS.get((button, pressed))
        if event is None:
            log.warn("no matching event found for button=%s, pressed=%s", button, pressed)
            return
        x, y = pointer
        dwFlags, dwData = event
        win32api.mouse_event(dwFlags, x, y, dwData, 0)

    def make_hello(self, source):
        capabilities = GTKServerBase.make_hello(self, source)
        capabilities["shadow"] = True
        capabilities["server_type"] = "Python/gtk2/win32-shadow"
        return capabilities

    def get_info(self, proto):
        info = GTKServerBase.get_info(self, proto)
        info["features.shadow"] = True
        info["server.type"] = "Python/gtk2/win32-shadow"
        return info


def main():
    from xpra.platform import init, clean
    try:
        init("Shadow-Test", "Shadow Server Screen Capture Test")
        rwm = Win32RootWindowModel(None)
        pngdata = rwm.take_screenshot()
        FILENAME = "screenshot.png"
        with open(FILENAME , "wb") as f:
            f.write(pngdata[4])
        print("saved screenshot as %s" % FILENAME)
    finally:
        #this will wait for input on win32:
        clean()

if __name__ == "__main__":
    main()

