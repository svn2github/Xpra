# This file is part of Xpra.
# Copyright (C) 2008, 2009 Nathaniel Smith <njs@pobox.com>
# Copyright (C) 2010-2014 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import time

import errno as pyerrno
from libc.stdint cimport uint64_t

from xpra.log import Logger
xshmlog = Logger("x11", "bindings", "ximage", "xshm")
log = Logger("x11", "bindings", "ximage")
xshmdebug = Logger("x11", "bindings", "ximage", "xshm", "verbose")
ximagedebug = Logger("x11", "bindings", "ximage", "verbose")


###################################
# Headers, python magic
###################################
cdef extern from "Python.h":
    ctypedef int Py_ssize_t

cdef extern from "../../codecs/buffers/buffers.h":
    object memory_as_pybuffer(void* ptr, Py_ssize_t buf_len, int readonly)
    int    object_as_buffer(object obj, const void ** buffer, Py_ssize_t * buffer_len)

cdef extern from "string.h":
    void * memcpy( void * destination, void * source, size_t num )

cdef extern from "sys/ipc.h":
    ctypedef struct key_t:
        pass
    key_t IPC_PRIVATE
    int IPC_CREAT
    int IPC_RMID

cdef extern from "sys/shm.h":
    int shmget(key_t __key, size_t __size, int __shmflg)
    void *shmat(int __shmid, const void *__shmaddr, int __shmflg)
    int shmdt (const void *__shmaddr)
    ctypedef struct shmid_ds:
        pass
    int shmctl(int shmid, int cmd, shmid_ds *buf)

cdef extern from "errno.h" nogil:
    int errno

cdef extern from "stdlib.h":
    void* malloc(size_t __size)
    void free(void* mem)

cdef extern from "X11/Xutil.h":
    pass


include "constants.pxi"
ctypedef unsigned long CARD32
ctypedef unsigned short CARD16
ctypedef unsigned char CARD8

cdef extern from "X11/X.h":
    unsigned long NoSymbol

cdef extern from "X11/Xlib.h":
    ctypedef struct Display:
        pass
    # To make it easier to translate stuff in the X header files into
    # appropriate pyrex declarations, without having to untangle the typedefs
    # over and over again, here are some convenience typedefs.  (Yes, CARD32
    # really is 64 bits on 64-bit systems.  Why? Because CARD32 was defined
    # as a long.. and a long is now 64-bit, it was easier to do this than
    # to change a lot of existing X11 client code)
    ctypedef CARD32 XID

    ctypedef int Bool
    ctypedef int Status
    ctypedef CARD32 Atom
    ctypedef XID Drawable
    ctypedef XID Window
    ctypedef XID Pixmap

    ctypedef CARD32 VisualID

    ctypedef struct Visual:
        void    *ext_data       #XExtData *ext_data;     /* hook for extension to hang data */
        VisualID visualid
        int c_class
        unsigned long red_mask
        unsigned long green_mask
        unsigned long blue_mask
        int bits_per_rgb
        int map_entries


    int XFree(void * data)

    Bool XQueryExtension(Display * display, char *name,
                         int *major_opcode_return, int *first_event_return, int *first_error_return)

    ctypedef struct XWindowAttributes:
        int x, y, width, height, depth, border_width
        Visual *visual

    Status XGetWindowAttributes(Display * display, Window w,
                                XWindowAttributes * attributes)

    ctypedef char* XPointer

    ctypedef struct XImage:
        int width
        int height
        int xoffset             # number of pixels offset in X direction
        int format              # XYBitmap, XYPixmap, ZPixmap
        char *data              # pointer to image data
        int byte_order          # data byte order, LSBFirst, MSBFirst
        int bitmap_unit         # quant. of scanline 8, 16, 32
        int bitmap_bit_order    # LSBFirst, MSBFirst
        int bitmap_pad          # 8, 16, 32 either XY or ZPixmap
        int depth               # depth of image
        int bytes_per_line      # accelerator to next scanline
        int bits_per_pixel      # bits per pixel (ZPixmap)
        unsigned long red_mask  # bits in z arrangement
        unsigned long green_mask
        unsigned long blue_mask
        XPointer *obdata
        void *funcs

    unsigned long AllPlanes
    int XYPixmap
    int ZPixmap
    int MSBFirst
    int LSBFirst

    XImage *XGetImage(Display *display, Drawable d,
            int x, int y, unsigned int width, unsigned int  height,
            unsigned long plane_mask, int format)

    void XDestroyImage(XImage *ximage)

    Status XGetGeometry(Display *display, Drawable d, Window *root_return,
                        int *x_return, int *y_return, unsigned int  *width_return, unsigned int *height_return,
                        unsigned int *border_width_return, unsigned int *depth_return)


cdef extern from "X11/extensions/Xcomposite.h":
    Bool XCompositeQueryExtension(Display *, int *, int *)
    Status XCompositeQueryVersion(Display *, int * major, int * minor)
    int XFreePixmap(Display *, Pixmap pixmap)
    Pixmap XCompositeNameWindowPixmap(Display *xdisplay, Window xwindow)

cdef extern from "X11/extensions/XShm.h":
    unsigned int ShmCompletion
    ctypedef struct ShmSeg:
        pass
    ctypedef struct XShmSegmentInfo:
        ShmSeg shmseg   # resource id
        int shmid       # kernel id
        char *shmaddr   # address in client
        Bool readOnly   # how the server should attach it

    XShmQueryExtension(Display *display)
    Bool XShmQueryVersion(Display *display, int *major, int *minor, Bool *pixmaps)

    Bool XShmAttach(Display *display, XShmSegmentInfo *shminfo)
    Bool XShmDetach(Display *display, XShmSegmentInfo *shminfo)

    XImage *XShmCreateImage(Display *display, Visual *visual,
                            unsigned int depth, int format, char *data,
                            XShmSegmentInfo *shminfo,
                            unsigned int width, unsigned int height)

    Bool XShmGetImage(Display *display, Drawable d, XImage *image,
                      int x, int y,
                      unsigned long plane_mask)

    int XShmGetEventBase(Display *display)



SBFirst = {
           MSBFirst : "MSBFirst",
           LSBFirst : "LSBFirst"
           }

cdef char *XRGB = "XRGB"
cdef char *BGRX = "BGRX"
cdef char *ARGB = "ARGB"
cdef char *BGRA = "BGRA"
cdef char *RGB = "RGB"
cdef char *RGBA = "RGBA"
cdef char *RGBX = "RGBX"

cdef char *RGB_FORMATS[8]
RGB_FORMATS[0] = XRGB
RGB_FORMATS[1] = BGRX
RGB_FORMATS[2] = ARGB
RGB_FORMATS[3] = BGRA
RGB_FORMATS[4] = RGB
RGB_FORMATS[5] = RGBA
RGB_FORMATS[6] = RGBX
RGB_FORMATS[7] = NULL


cdef int ximage_counter = 0

cdef class XImageWrapper:
    """
        Presents X11 image pixels as in ImageWrapper
    """

    cdef XImage *image                              #@DuplicatedSignature
    cdef int x
    cdef int y
    cdef int width                                  #@DuplicatedSignature
    cdef int height                                 #@DuplicatedSignature
    cdef int depth                                  #@DuplicatedSignature
    cdef int rowstride
    cdef int planes
    cdef int thread_safe
    cdef char *pixel_format
    cdef char *pixels
    cdef object del_callback
    cdef uint64_t timestamp

    def __cinit__(self, int x, int y, int width, int height):
        self.image = NULL
        self.pixels = NULL
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.pixel_format = ""
        self.rowstride = 0
        self.planes = 0
        self.thread_safe = 0
        self.timestamp = int(time.time()*1000)

    cdef set_image(self, XImage* image):
        global ximage_counter
        ximage_counter += 1
        self.thread_safe = 0
        self.image = image
        self.rowstride = self.image.bytes_per_line
        self.depth = self.image.depth
        if self.depth==24:
            if self.image.byte_order==MSBFirst:
                self.pixel_format = XRGB
            else:
                self.pixel_format = BGRX
        elif self.depth==32:
            if self.image.byte_order==MSBFirst:
                self.pixel_format = ARGB
            else:
                self.pixel_format = BGRA
        else:
            raise Exception("invalid image depth: %s bpp" % self.depth)

    def __repr__(self):
        return "XImageWrapper(%s: %s, %s, %s, %s)" % (self.pixel_format, self.x, self.y, self.width, self.height)

    def get_geometry(self):
        return self.x, self.y, self.width, self.height, self.depth

    def get_x(self):
        return self.x

    def get_y(self):
        return self.y

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def get_rowstride(self):
        return self.rowstride

    def get_planes(self):
        return self.planes

    def get_depth(self):
        return self.depth

    def get_size(self):
        return self.rowstride * self.height

    def get_pixel_format(self):
        return self.pixel_format

    def get_pixels(self):
        if self.pixels!=NULL:
            return self.get_char_pixels()
        return self.get_image_pixels()

    cdef get_char_pixels(self):
        assert self.pixels!=NULL
        return memory_as_pybuffer(self.pixels, self.get_size(), False)

    cdef get_image_pixels(self):
        assert self.image!=NULL
        return memory_as_pybuffer(self.image.data, self.get_size(), False)

    def is_thread_safe(self):
        return self.thread_safe

    def get_timestamp(self):
        """ time in millis """
        return self.timestamp


    def set_timestamp(self, timestamp):
        self.timestamp = timestamp

    def set_rowstride(self, rowstride):
        self.rowstride = rowstride

    def set_pixel_format(self, pixel_format):
        assert pixel_format is not None
        cdef int i =0
        while RGB_FORMATS[i]!=NULL and RGB_FORMATS[i]!=pixel_format:
            i +=1
        assert RGB_FORMATS[i]!=NULL, "invalid pixel format: %s" % pixel_format
        self.pixel_format = RGB_FORMATS[i]

    def set_pixels(self, pixels):
        """ overrides the context of the image with the given pixels buffer """
        cdef const unsigned char * buf = NULL
        cdef Py_ssize_t buf_len = 0
        if self.pixels!=NULL:
            free(self.pixels)
            self.pixels = NULL
        #Note: we can't free the XImage, because it may
        #still be used somewhere else (see XShmWrapper)
        assert object_as_buffer(pixels, <const void**> &buf, &buf_len)==0
        self.pixels = <char *> malloc(buf_len)
        assert self.pixels!=NULL
        memcpy(self.pixels, buf, buf_len)
        if self.image==NULL:
            self.thread_safe = 1
            #we can only mark this object as thread safe
            #if we have already freed the XImage
            #(since it needs to be freed from the UI thread)


    def free(self):                                     #@DuplicatedSignature
        ximagedebug("%s.free()", self)
        self.free_image()
        self.free_pixels()

    cdef free_image(self):
        ximagedebug("%s.free_image() image=%#x", self, <unsigned long> self.image)
        if self.image!=NULL:
            XDestroyImage(self.image)
            self.image = NULL
            global ximage_counter
            ximage_counter -= 1

    cdef free_pixels(self):
        ximagedebug("%s.free_pixels() pixels=%#x", self, <unsigned long> self.pixels)
        if self.pixels!=NULL:
            free(self.pixels)
            self.pixels = NULL


cdef class XShmWrapper(object):
    cdef Display *display                              #@DuplicatedSignature
    cdef Visual *visual
    cdef Window window
    cdef int width
    cdef int height
    cdef int depth
    cdef XShmSegmentInfo shminfo
    cdef XImage *image
    cdef int ref_count
    cdef Bool got_image
    cdef Bool closed

    cdef init(self, Display *display, Window xwindow, Visual *visual, int width, int height, int depth):
        self.display = display
        self.window = xwindow
        self.visual = visual
        self.width = width
        self.height = height
        self.depth = depth

    def setup(self):
        #returns:
        # (init_ok, may_retry_this_window, XShm_global_failure)
        cdef size_t size
        cdef Bool a
        self.ref_count = 0
        self.closed = False
        self.shminfo.shmaddr = <char *> -1

        self.image = XShmCreateImage(self.display, self.visual, self.depth,
                          ZPixmap, NULL, &self.shminfo,
                          self.width, self.height)
        xshmdebug("XShmWrapper.setup() XShmCreateImage(%sx%s-%s) %s", self.width, self.height, self.depth, self.image!=NULL)
        if self.image==NULL:
            xshmlog.error("XShmWrapper.setup() XShmCreateImage(%sx%s-%s) failed!", self.width, self.height, self.depth)
            self.cleanup()
            #if we cannot create an XShm XImage, we may try again
            #(it could be dimensions are too big?)
            return False, True, False
        # Get the shared memory:
        # (include an extra line to ensure we can read rowstride at a time,
        #  even on the last line, without reading past the end of the buffer)
        size = self.image.bytes_per_line * (self.image.height + 1)
        self.shminfo.shmid = shmget(IPC_PRIVATE, size, IPC_CREAT | 0777)
        xshmdebug("XShmWrapper.setup() shmget(PRIVATE, %s bytes, %s) shmid=%s", size, IPC_CREAT | 0777, self.shminfo.shmid)
        if self.shminfo.shmid < 0:
            xshmlog.error("XShmWrapper.setup() shmget(PRIVATE, %s bytes, %s) failed, bytes_per_line=%s, width=%s, height=%s", size, IPC_CREAT | 0777, self.image.bytes_per_line, self.width, self.height)
            self.cleanup()
            #only try again if we get EINVAL,
            #the other error codes probably mean this is never going to work..
            return False, errno==pyerrno.EINVAL, errno!=pyerrno.EINVAL
        # Attach:
        self.image.data = <char *> shmat(self.shminfo.shmid, NULL, 0)
        self.shminfo.shmaddr = self.image.data
        xshmdebug("XShmWrapper.setup() shmat(%s, NULL, 0) %s", self.shminfo.shmid, self.shminfo.shmaddr != <char *> -1)
        if self.shminfo.shmaddr == <char *> -1:
            xshmlog.error("XShmWrapper.setup() shmat(%s, NULL, 0) failed!", self.shminfo.shmid)
            self.cleanup()
            #we may try again with this window, or any other window:
            #(as this really shouldn't happen at all)
            return False, True, False

        # set as read/write, and attach to the display:
        self.shminfo.readOnly = False
        a = XShmAttach(self.display, &self.shminfo)
        xshmdebug("XShmWrapper.setup() XShmAttach(..) %s", bool(a))
        if not a:
            xshmlog.error("XShmWrapper.setup() XShmAttach(..) failed!")
            self.cleanup()
            #we may try again with this window, or any other window:
            #(as this really shouldn't happen at all)
            return False, True, False
        return True, True, False

    def get_size(self):                                     #@DuplicatedSignature
        return self.width, self.height

    def get_image(self, Pixmap xpixmap, int x, int y, int w, int h):
        assert self.image!=NULL, "cannot retrieve image wrapper: XImage is NULL!"
        if self.closed:
            return None
        xshmdebug("XShmWrapper.get_image%s", (xpixmap, x, y, w, h))
        if x>=self.width or y>=self.height:
            xshmlog("XShmWrapper.get_image%s position outside image dimensions %sx%s", (xpixmap, x, y, w, h), self.width, self.height)
            return None
        #clamp size to image size:
        if x+w>self.width:
            w = self.width-x
        if y+h>self.height:
            h = self.height-y
        if not self.got_image:
            if not XShmGetImage(self.display, xpixmap, self.image, 0, 0, 0xFFFFFFFF):
                xshmlog("XShmWrapper.get_image%s XShmGetImage failed!", (xpixmap, x, y, w, h))
                return None
            self.got_image = True
        self.ref_count += 1
        cdef XShmImageWrapper imageWrapper
        imageWrapper = XShmImageWrapper(x, y, w, h)
        imageWrapper.set_image(self.image)
        imageWrapper.set_free_callback(self.free_image_callback)
        xshmdebug("XShmWrapper.get_image%s ref_count=%s, returning %s", (xpixmap, x, y, w, h), self.ref_count, imageWrapper)
        return imageWrapper

    def discard(self):
        #force next get_image call to get a new image from the server
        self.got_image = False

    def __dealloc__(self):                              #@DuplicatedSignature
        xshmdebug("XShmWrapper.__dealloc__() ref_count=%s", self.ref_count)
        self.cleanup()

    def cleanup(self):
        #ok, we want to free resources... problem is,
        #we may have handed out some XShmImageWrappers
        #and they will point to our Image XShm area.
        #so we have to wait until *they* are freed,
        #and rely on them telling us via the free_image_callback.
        xshmdebug("XShmWrapper.cleanup() ref_count=%s", self.ref_count)
        self.closed = True
        if self.ref_count==0:
            self.free()

    def free_image_callback(self):                               #@DuplicatedSignature
        self.ref_count -= 1
        xshmdebug("XShmWrapper.free_image_callback() closed=%s, new ref_count=%s", self.closed, self.ref_count)
        if self.closed and self.ref_count==0:
            self.free()

    cdef free(self):                                     #@DuplicatedSignature
        assert self.ref_count==0, "XShmWrapper %s cannot be freed: still has a ref count of %s" % (self, self.ref_count)
        assert self.closed, "XShmWrapper %s cannot be freed: it is not closed yet" % self
        has_shm = self.shminfo.shmaddr!=<char *> -1
        xshmdebug("XShmWrapper.free() has_shm=%s, image=%#x, shmid=%s", has_shm, <unsigned long> self.image, self.shminfo.shmid)
        if has_shm:
            XShmDetach(self.display, &self.shminfo)
        if self.image!=NULL:
            XDestroyImage(self.image)
            self.image = NULL
        if has_shm:
            shmctl(self.shminfo.shmid, IPC_RMID, NULL)
            shmdt(self.shminfo.shmaddr)
            self.shminfo.shmaddr = <char *> -1
            self.shminfo.shmid = -1


cdef class XShmImageWrapper(XImageWrapper):

    cdef object free_callback

    def __init__(self, *args):                      #@DuplicatedSignature
        self.free_callback = None

    def __repr__(self):                              #@DuplicatedSignature
        return "XShmImageWrapper(%s: %s, %s, %s, %s)" % (self.pixel_format, self.x, self.y, self.width, self.height)

    cdef get_image_pixels(self):                     #@DuplicatedSignature
        cdef char *offset
        xshmdebug("XShmImageWrapper.get_image_pixels() self=%s", self)
        assert self.image!=NULL and self.height>0
        #calculate offset (assuming 4 bytes "pixelstride"):
        offset = self.image.data + (self.y * self.rowstride) + (4 * self.x)
        cdef Py_ssize_t size = self.height * self.rowstride
        return memory_as_pybuffer(offset, size, False)

    def free(self):                                 #@DuplicatedSignature
        #ensure we never try to XDestroyImage:
        self.image = NULL
        self.free_pixels()
        cb = self.free_callback
        if cb:
            self.free_callback = None
            cb()
        xshmdebug("XShmImageWrapper.free() done, callback=%s", cb)

    cdef set_free_callback(self, object callback):
        self.free_callback = callback


cdef int xpixmap_counter = 0

cdef class PixmapWrapper(object):
    cdef Display *display
    cdef Pixmap pixmap
    cdef int width                          #@DuplicatedSignature
    cdef int height                         #@DuplicatedSignature

    "Reference count an X Pixmap that needs explicit cleanup."
    cdef init(self, Display *display, Pixmap pixmap, int width, int height):     #@DuplicatedSignature
        self.display = display
        self.pixmap = pixmap
        self.width = width
        self.height = height
        global xpixmap_counter
        xpixmap_counter += 1
        ximagedebug("%s xpixmap counter: %i", self, xpixmap_counter)

    def __repr__(self):                     #@DuplicatedSignature
        return "PixmapWrapper(%#x, %i, %i)" % (self.pixmap, self.width, self.height)

    def get_width(self):                    #@DuplicatedSignature
        return self.width

    def get_height(self):                   #@DuplicatedSignature
        return self.height

    def get_pixmap(self):
        return self.pixmap

    def get_image(self, int x, int y, int width, int height):                #@DuplicatedSignature
        if not self.pixmap:
            log.warn("%s.get_image%s", self, (x, y, width, height))
            return  None
        ximagedebug("%s.get_image%s width=%s, height=%s", self, (x, y, width, height), self.width, self.height)
        if x>=self.width or y>=self.height:
            log("%s.get_image%s position outside image dimensions %sx%s", self, (x, y, width, height), self.width, self.height)
            return None
        #clamp size to image size:
        if x+width>self.width:
            width = self.width-x
        if y+height>self.height:
            height = self.height-y
        return get_image(self.display, self.pixmap, x, y, width, height)

    def __dealloc__(self):                  #@DuplicatedSignature
        self.do_cleanup()

    cdef do_cleanup(self):                  #@DuplicatedSignature
        if self.pixmap!=0:
            XFreePixmap(self.display, self.pixmap)
            self.pixmap = 0
            global xpixmap_counter
            xpixmap_counter -= 1

    def cleanup(self):                      #@DuplicatedSignature
        ximagedebug("%s.cleanup() pixmap=%#x", self, self.pixmap)
        self.do_cleanup()



cdef get_image(Display * display, Pixmap pixmap, int x, int y, int width, int height):
    cdef XImage* ximage
    ximage = XGetImage(display, pixmap, x, y, width, height, AllPlanes, ZPixmap)
    #log.info("get_pixels(..) ximage==NULL : %s", ximage==NULL)
    if ximage==NULL:
        log("get_image(..) failed to get XImage for X11 pixmap %#x", pixmap)
        return None
    xi = XImageWrapper(x, y, width, height)
    xi.set_image(ximage)
    global ximage_counter
    ximagedebug("%s ximage counter: %i", xi, ximage_counter)
    return xi


cdef xcomposite_name_window_pixmap(Display * xdisplay, Window xwindow):
    cdef Window root_window
    cdef int x, y
    cdef unsigned int width, height, border, depth
    cdef Status status
    cdef Pixmap xpixmap
    cdef PixmapWrapper pw
    xpixmap = XCompositeNameWindowPixmap(xdisplay, xwindow)
    if xpixmap==XNone:
        return None
    status = XGetGeometry(xdisplay, xpixmap, &root_window,
                        &x, &y, &width, &height, &border, &depth)
    if status==0:
        log("failed to get pixmap dimensions for %#x", xpixmap)
        XFreePixmap(xdisplay, xpixmap)
        return None
    pw = PixmapWrapper()
    pw.init(xdisplay, xpixmap, width, height)
    return pw


from core_bindings cimport X11CoreBindings

cdef class XImageBindings(X11CoreBindings):

    def get_XShmWrapper(self, xwindow):
        cdef XWindowAttributes attrs
        if XGetWindowAttributes(self.display, xwindow, &attrs)==0:
            return None
        xshm = XShmWrapper()
        xshm.init(self.display, xwindow, attrs.visual, attrs.width, attrs.height, attrs.depth)
        return xshm

    def get_ximage(self, xpixmap, x, y, width, height):      #@DuplicatedSignature
        return get_image(self.display, xpixmap, x, y, width, height)

    def get_xcomposite_pixmap(self, xwindow):
        return xcomposite_name_window_pixmap(self.display, xwindow)
