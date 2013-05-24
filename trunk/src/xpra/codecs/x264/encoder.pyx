# This file is part of Xpra.
# Copyright (C) 2012, 2013 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import os
from libc.stdlib cimport free

from xpra.codecs.codec_constants import get_subsampling_divs

DEFAULT_INITIAL_QUALITY = 70
DEFAULT_INITIAL_SPEED = 20
ALL_PROFILES = ["baseline", "main", "high", "high10", "high422", "high444"]
I420_PROFILES = ALL_PROFILES[:]
I422_PROFILES = ["high422", "high444"]
I444_PROFILES = ["high444"]
DEFAULT_I420_PROFILE = "baseline"
DEFAULT_I422_PROFILE = "high422"
DEFAULT_I444_PROFILE = "high444"
DEFAULT_I422_QUALITY = 70
DEFAULT_I422_MIN_QUALITY = 50
DEFAULT_I444_QUALITY = 90
DEFAULT_I444_MIN_QUALITY = 75

cdef extern from "string.h":
    void * memcpy ( void * destination, void * source, size_t num )
    void * memset ( void * ptr, int value, size_t num )

cdef extern from *:
    ctypedef unsigned long size_t

cdef extern from "Python.h":
    ctypedef int Py_ssize_t
    ctypedef object PyObject
    ctypedef void** const_void_pp "const void**"
    int PyObject_AsReadBuffer(object obj, void ** buffer, Py_ssize_t * buffer_len) except -1

ctypedef unsigned char uint8_t
ctypedef void x264lib_ctx
ctypedef void x264_picture_t
cdef extern from "x264lib.h":
    void* xmemalign(size_t size) nogil
    void xmemfree(void* ptr) nogil

    int get_x264_build_no()

    x264lib_ctx* init_encoder(int width, int height, char *rgb_format,
                              int initial_quality, int initial_speed,
                              int supports_csc_option,
                              int I422_quality, int I444_quality,
                              int I422_min, int I444_min,
                              char *i420_profile, char *i422_profile, char *i444_profile)
    void clean_encoder(x264lib_ctx *context)
    x264_picture_t* csc_image_rgb2yuv(x264lib_ctx *ctx, uint8_t *input, int stride)
    int compress_image(x264lib_ctx *ctx, x264_picture_t *pic_in, uint8_t **out, int *outsz) nogil
    int get_encoder_pixel_format(x264lib_ctx *ctx)
    int get_encoder_quality(x264lib_ctx *ctx)
    int get_encoder_speed(x264lib_ctx *ctx)

    void set_encoding_speed(x264lib_ctx *context, int pct)
    void set_encoding_quality(x264lib_ctx *context, int pct)


def get_version():
    return get_x264_build_no()


cdef class Encoder:
    cdef int frames
    cdef int supports_options
    cdef x264lib_ctx *context
    cdef int width
    cdef int height
    cdef char* rgb_format

    def init_context(self, int width, int height, rgb_format, options):    #@DuplicatedSignature
        self.width = width
        self.height = height
        self.rgb_format = rgb_format
        self.frames = 0
        self.supports_options = int(options.get("client_options", False))
        I420_profile = self._get_profile(options, "I420", DEFAULT_I420_PROFILE, I420_PROFILES)
        I422_profile = self._get_profile(options, "I422", DEFAULT_I422_PROFILE, I422_PROFILES)
        I444_profile = self._get_profile(options, "I444", DEFAULT_I444_PROFILE, I444_PROFILES)
        I422_quality = self._get_quality(options, "I422", DEFAULT_I422_QUALITY)
        I444_quality = self._get_quality(options, "I444", DEFAULT_I444_QUALITY)
        I422_min = self._get_min_quality(options, "I422", DEFAULT_I422_MIN_QUALITY)
        I444_min = self._get_min_quality(options, "I444", DEFAULT_I444_MIN_QUALITY)
        initial_quality = options.get("initial_quality", options.get("quality", DEFAULT_INITIAL_QUALITY))
        initial_speed = options.get("initial_speed", options.get("speed", DEFAULT_INITIAL_SPEED))
        initial_quality = min(100, max(0, initial_quality))
        initial_speed = min(100, max(0, initial_speed))
        self.context = init_encoder(width, height, rgb_format,
                                    initial_quality, initial_speed,
                                    int(self.supports_options),
                                    int(I422_quality), int(I444_quality),
                                    int(I422_min), int(I444_min),
                                    I420_profile, I422_profile, I444_profile)

    def is_closed(self):
        return self.context==NULL

    def __dealloc__(self):
        self.clean()

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def get_type(self):
        return  "x264"

    def get_rgb_format(self):
        return self.rgb_format

    def _get_profile(self, options, csc_mode, default_value, valid_options):
        #try the environment as a default, fallback to hardcoded default:
        profile = os.environ.get("XPRA_X264_%s_PROFILE" % csc_mode, default_value)
        #now see if the client has requested a different value:
        profile = options.get("x264.%s.profile" % csc_mode, profile)
        if profile not in valid_options:
            print("invalid %s profile: %s" % (csc_mode, profile))
            return default_value
        return profile

    def _get_min_quality(self, options, csc_mode, default_value):
        #try the environment as a default, fallback to hardcoded default:
        min_quality = int(os.environ.get("XPRA_X264_%s_MIN_QUALITY" % csc_mode, default_value))
        #now see if the client has requested a different value:
        min_quality = options.get("x264.%s.min_quality" % csc_mode, min_quality)
        #enforce valid range:
        return min(100, max(-1, min_quality))

    def _get_quality(self, options, csc_mode, default_value):
        #try the environment as a default, fallback to hardcoded default:
        quality = int(os.environ.get("XPRA_X264_%s_QUALITY" % csc_mode, default_value))
        #now see if the client has requested a different value:
        quality = options.get("x264.%s.quality" % csc_mode, quality)
        #enforce valid range:
        return min(100, max(-1, quality))

    def clean(self):                        #@DuplicatedSignature
        if self.context!=NULL:
            clean_encoder(self.context)
            self.context = NULL

    def get_client_options(self, options):
        csc_pf = get_encoder_pixel_format(self.context)
        client_options = {
                "csc_pixel_format" : csc_pf,
                "frame" : self.frames
                }
        q = client_options.get("quality", -1)
        if q<0:
            q = get_encoder_quality(self.context)
        client_options["quality"] = q
        s = client_options.get("speed", -1)
        if s<0:
            s = get_encoder_speed(self.context)
        client_options["speed"] = s
        return  client_options

    def compress_image(self, image, options):
        cdef x264_picture_t *pic_in = NULL
        cdef const uint8_t *pic_buf = NULL
        cdef Py_ssize_t pic_buf_len = 0
        cdef int quality_override = options.get("quality", -1)
        cdef int speed_override = options.get("speed", -1)
        cdef int saved_quality = get_encoder_quality(self.context)
        cdef int saved_speed = get_encoder_speed(self.context)
        if speed_override>=0 and saved_speed!=speed_override:
            set_encoding_speed(self.context, speed_override)
        if quality_override>=0 and saved_quality!=quality_override:
            set_encoding_quality(self.context, quality_override)
        assert self.context!=NULL
        #colourspace conversion with gil held:
        input = image.get_pixels()
        rowstride = image.get_rowstride()
        PyObject_AsReadBuffer(input, <const_void_pp> &pic_buf, &pic_buf_len)
        pic_in = csc_image_rgb2yuv(self.context, pic_buf, rowstride)
        assert pic_in!=NULL, "colourspace conversion failed"
        try:
            return self.do_compress_image(pic_in), self.get_client_options(options)
        finally:
            if speed_override>=0 and saved_speed!=speed_override:
                set_encoding_speed(self.context, saved_speed)
            if quality_override>=0 and saved_quality!=quality_override:
                set_encoding_quality(self.context, saved_quality)

    cdef do_compress_image(self, x264_picture_t *pic_in):
        #actual compression (no gil):
        cdef int i
        cdef uint8_t *cout
        cdef int coutsz
        with nogil:
            i = compress_image(self.context, pic_in, &cout, &coutsz)
        if i!=0:
            return None
        coutv = (<char *>cout)[:coutsz]
        self.frames += 1
        return  coutv

    def set_encoding_speed(self, int pct):
        assert pct>=0 and pct<=100, "invalid percentage: %s" % pct
        assert self.context!=NULL, "context is closed!"
        set_encoding_speed(self.context, pct)

    def set_encoding_quality(self, int pct):
        assert pct>=0 and pct<=100, "invalid percentage: %s" % pct
        assert self.context!=NULL, "context is closed!"
        set_encoding_quality(self.context, pct)
