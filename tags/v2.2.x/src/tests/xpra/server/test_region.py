#!/usr/bin/env python
# This file is part of Xpra.
# Copyright (C) 2013 Antoine Martin <antoine@devloop.org.uk>
# Xpra is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

import time
import gobject
gobject.threads_init()

from xpra.server.window.region import rectangle, add_rectangle, remove_rectangle, merge_all, contains_rect #@UnresolvedImport (cython)


#collected with the server "-d encoding"
#then converted to rectangles with:
#grep damage\( damage.txt | grep -v WindowModel | sed 's/.*damage(/(/g' | sed 's/, {}.*/),/g'  | awk '{print $1"\t"$2"\t"$3"\t"$4}'
R1 = [
    (2348,    59,    16,    1412),
    (2348,    59,    16,    1412),
    (146,    1456,    8,    15),
    (146,    1456,    8,    15),
    (0,    59,    2348,    1397),
    (0,    1456,    146,    15),
    (154,    1456,    2194,    15),
    (0,    1471,    2348,    17),
    (34,    61,    8,    15),
    (42,    61,    40,    15),
    (82,    61,    392,    15),
    (34,    76,    96,    15),
    (138,    76,    8,    15),
    (154,    76,    16,    15),
    (170,    76,    112,    15),
    (282,    76,    8,    15),
    (298,    76,    8,    15),
    (306,    76,    16,    15),
    (34,    91,    16,    15),
    (58,    91,    192,    15),
    (250,    91,    40,    15),
    (290,    91,    16,    15),
    (66,    106,    168,    15),
    (234,    106,    48,    15),
    (282,    106,    8,    15),
    (298,    106,    32,    15),
    (330,    106,    16,    15),
    (66,    121,    392,    15),
    (458,    121,    112,    15),
    (570,    121,    8,    15),
    (586,    121,    16,    15),
    (602,    121,    16,    15),
    (626,    121,    40,    15),
    (666,    121,    8,    15),
    (682,    121,    48,    15),
    (730,    121,    16,    15),
    (754,    121,    32,    15),
    (786,    121,    16,    15),
    (34,    136,    48,    15),
    (90,    136,    280,    15),
    (2,    181,    24,    15),
    (34,    181,    64,    15),
    (98,    181,    56,    15),
    (162,    181,    32,    15),
    (202,    181,    56,    15),
    (34,    196,    16,    15),
    (58,    196,    56,    15),
    (114,    196,    72,    15),
    (194,    196,    16,    15),
    (218,    196,    112,    15),
    (338,    196,    16,    15),
    (362,    196,    32,    15),
    (394,    196,    8,    15),
    (66,    211,    80,    15),
    (154,    211,    8,    15),
    (170,    211,    40,    15),
    (2,    241,    24,    15),
    (34,    241,    136,    15),
    (170,    241,    24,    15),
    (34,    256,    408,    15),
    (34,    271,    16,    15),
    (58,    271,    192,    15),
    (250,    271,    40,    15),
    (290,    271,    16,    15),
    (66,    286,    560,    15),
    (66,    301,    32,    15),
    (106,    301,    32,    15),
    (138,    301,    8,    15),
    (146,    301,    112,    15),
    (258,    301,    8,    15),
    (274,    301,    16,    15),
    (298,    301,    16,    15),
    (98,    316,    32,    15),
    (138,    316,    8,    15),
    (154,    316,    64,    15),
    (66,    331,    16,    15),
    (90,    331,    32,    15),
    (130,    331,    24,    15),
    (162,    331,    24,    15),
    (186,    331,    160,    15),
    (346,    331,    104,    15),
    (450,    331,    16,    15),
    (98,    346,    48,    15),
    (154,    346,    104,    15),
    (66,    361,    48,    15),
    (122,    361,    72,    15),
    (34,    376,    16,    15),
    (58,    376,    144,    15),
    (202,    376,    64,    15),
    (266,    376,    24,    15),
    (290,    376,    8,    15),
    (298,    376,    8,    15),
    (66,    391,    24,    15),
    (90,    391,    8,    15),
    (98,    406,    160,    15),
    (98,    421,    48,    15),
    (154,    421,    104,    15),
    (266,    421,    8,    15),
    (282,    421,    152,    15),
    (434,    421,    8,    15),
    (442,    421,    8,    15),
    (66,    436,    48,    15),
    (114,    436,    8,    15),
    (98,    451,    48,    15),
    (154,    451,    80,    15),
    (34,    466,    16,    15),
    (58,    466,    144,    15),
    (202,    466,    72,    15),
    (274,    466,    24,    15),
    (298,    466,    8,    15),
    (306,    466,    8,    15),
    (66,    481,    48,    15),
    (122,    481,    72,    15),
    (34,    496,    16,    15),
    (58,    496,    192,    15),
    (250,    496,    40,    15),
    (290,    496,    16,    15),
    (66,    511,    24,    15),
    (90,    511,    8,    15),
    (98,    526,    48,    15),
    (154,    526,    24,    15),
    (274,    526,    144,    15),
    (98,    541,    8,    15),
    (114,    541,    8,    15),
    (130,    541,    72,    15),
    (98,    556,    24,    15),
    (130,    556,    16,    15),
    (154,    556,    16,    15),
    (178,    556,    208,    15),
    (130,    571,    16,    15),
    (154,    571,    8,    15),
    (170,    571,    128,    15),
    (298,    571,    24,    15),
    (322,    571,    8,    15),
    (130,    586,    16,    15),
    (154,    586,    24,    15),
    (178,    586,    8,    15),
    (186,    586,    8,    15),
    (162,    601,    48,    15),
    (218,    601,    200,    15),
    (130,    616,    48,    15),
    (186,    616,    80,    15),
    (66,    631,    48,    15),
    (114,    631,    8,    15),
    (98,    646,    32,    15),
    (66,    661,    48,    15),
    (122,    661,    152,    15),
    (34,    676,    16,    15),
    (58,    676,    144,    15),
    (202,    676,    40,    15),
    (242,    676,    24,    15),
    (266,    676,    8,    15),
    (274,    676,    8,    15),
    (66,    691,    48,    15),
    (122,    691,    40,    15),
    (34,    706,    16,    15),
    (58,    706,    144,    15),
    (202,    706,    56,    15),
    (258,    706,    24,    15),
    (282,    706,    8,    15),
    (298,    706,    24,    15),
    (330,    706,    56,    15),
    (386,    706,    80,    15),
    (474,    706,    160,    15),
    (634,    706,    16,    15),
    (66,    721,    48,    15),
    (122,    721,    80,    15),
    (210,    721,    8,    15),
    (226,    721,    8,    15),
    (234,    721,    24,    15),
    (258,    721,    296,    15),
    (34,    736,    48,    15),
    (90,    736,    96,    15),
    (2,    781,    120,    15),
    (130,    781,    8,    15),
    (146,    781,    176,    15),
    (2,    796,    24,    15),
    (34,    796,    136,    15),
    (170,    796,    80,    15),
    (250,    796,    32,    15),
    (282,    796,    16,    15),
    (34,    811,    48,    15),
    (90,    811,    120,    15),
    (34,    826,    40,    15),
    (82,    826,    8,    15),
    (98,    826,    248,    15),
    (34,    841,    16,    15),
    (58,    841,    72,    15),
    (66,    856,    120,    15),
    (194,    856,    80,    15),
    (274,    856,    8,    15),
    (290,    856,    144,    15),
    (66,    871,    120,    15),
    (194,    871,    80,    15),
    (274,    871,    8,    15),
    (290,    871,    168,    15),
    (66,    886,    120,    15),
    (194,    886,    96,    15),
    (290,    886,    8,    15),
    (306,    886,    272,    15),
    (66,    901,    120,    15),
    (194,    901,    96,    15),
    (290,    901,    8,    15),
    (306,    901,    264,    15),
    (570,    901,    56,    15),
    (626,    901,    16,    15),
    (66,    916,    120,    15),
    (194,    916,    88,    15),
    (282,    916,    8,    15),
    (298,    916,    112,    15),
    (66,    931,    120,    15),
    (194,    931,    88,    15),
    (282,    931,    8,    15),
    (298,    931,    192,    15),
    (490,    931,    8,    15),
    (498,    931,    16,    15),
    (66,    946,    120,    15),
    (194,    946,    80,    15),
    (274,    946,    8,    15),
    (290,    946,    160,    15),
    (66,    961,    24,    15),
    (90,    961,    8,    15),
    (98,    976,    32,    15),
    (138,    976,    48,    15),
    (194,    976,    48,    15),
    (250,    976,    88,    15),
    (346,    976,    16,    15),
    (370,    976,    112,    15),
    (66,    991,    48,    15),
    (114,    991,    8,    15),
    (98,    1006,    112,    15),
    (218,    1006,    8,    15),
    (234,    1006,    72,    15),
    (66,    1021,    120,    15),
    (194,    1021,    128,    15),
    (322,    1021,    8,    15),
    (338,    1021,    144,    15),
    (482,    1021,    8,    15),
    (490,    1021,    16,    15),
    (66,    1036,    120,    15),
    (194,    1036,    128,    15),
    (322,    1036,    8,    15),
    (338,    1036,    120,    15),
    (66,    1051,    120,    15),
    (194,    1051,    144,    15),
    (338,    1051,    8,    15),
    (354,    1051,    184,    15),
    (66,    1066,    120,    15),
    (194,    1066,    128,    15),
    (322,    1066,    8,    15),
    (338,    1066,    168,    15),
    (66,    1081,    120,    15),
    (194,    1081,    120,    15),
    (314,    1081,    8,    15),
    (330,    1081,    24,    15),
    (362,    1081,    32,    15),
    (394,    1081,    128,    15),
    (522,    1081,    48,    15),
    (570,    1081,    8,    15),
    (586,    1081,    16,    15),
    (602,    1081,    24,    15),
    (34,    1096,    176,    15),
    (218,    1096,    128,    15),
    (2,    1141,    24,    15),
    (34,    1141,    208,    15),
    (242,    1141,    24,    15),
    (34,    1156,    56,    15),
    (98,    1156,    8,    15),
    (114,    1156,    16,    15),
    (34,    1171,    32,    15),
    (74,    1171,    32,    15),
    (106,    1171,    8,    15),
    (114,    1171,    232,    15),
    (346,    1171,    8,    15),
    (362,    1171,    32,    15),
    (394,    1171,    8,    15),
    (410,    1171,    16,    15),
    (434,    1171,    16,    15),
    (66,    1186,    24,    15),
    (98,    1186,    32,    15),
    (138,    1186,    16,    15),
    (162,    1186,    16,    15),
    (98,    1201,    8,    15),
    (114,    1201,    8,    15),
    (130,    1201,    96,    15),
    (98,    1216,    16,    15),
    (122,    1216,    24,    15),
    (146,    1216,    40,    15),
    (186,    1216,    8,    15),
    (194,    1216,    8,    15),
    (130,    1231,    64,    15),
    (98,    1246,    16,    15),
    (122,    1246,    16,    15),
    (138,    1246,    8,    15),
    (146,    1246,    8,    15),
    (162,    1246,    16,    15),
    (186,    1246,    8,    15),
    (194,    1246,    24,    15),
    (218,    1246,    8,    15),
    (234,    1246,    24,    15),
    (258,    1246,    16,    15),
    (130,    1261,    64,    15),
    (98,    1276,    136,    15),
    (34,    1291,    48,    15),
    (90,    1291,    56,    15),
    (2,    1321,    24,    15),
    (34,    1321,    104,    15),
    (138,    1321,    24,    15),
    (34,    1336,    40,    15),
    (82,    1336,    8,    15),
    (98,    1336,    8,    15),
    (130,    1351,    80,    15),
    (218,    1351,    8,    15),
    (234,    1351,    72,    15),
    (306,    1351,    8,    15),
    (130,    1366,    168,    15),
    (306,    1366,    8,    15),
    (322,    1366,    72,    15),
    (98,    1381,    8,    15),
    (34,    1396,    120,    15),
    (34,    1411,    32,    15),
    (74,    1411,    8,    15),
    (90,    1411,    136,    15),
    (226,    1411,    144,    15),
    (370,    1411,    8,    15),
    (386,    1411,    48,    15),
    (434,    1411,    32,    15),
    (466,    1411,    8,    15),
    (482,    1411,    184,    15),
    (674,    1411,    184,    15),
    (866,    1411,    48,    15),
    (914,    1411,    32,    15),
    (946,    1411,    8,    15),
    (34,    1426,    40,    15),
    (82,    1426,    16,    15),
    (106,    1426,    8,    15),
    (122,    1426,    144,    15),
    (34,    1441,    16,    15),
    (58,    1441,    136,    15),
    (194,    1441,    8,    15),
    (202,    1441,    8,    15),
    (66,    1456,    40,    15),
    (106,    1456,    8,    15),
    (114,    1456,    352,    15),
    (474,    1456,    8,    15),
    (490,    1456,    128,    15),
    (2202,    1471,    40,    15),
    (2314,    1471,    24,    15),
    (2338,    1471,    8,    15),
    (146,    76,    8,    15),
    (2348,    59,    16,    1412),
    (146,    76,    8,    15),
    (0,    59,    2348,    17),
    (0,    76,    146,    15),
    (154,    76,    2194,    15),
    (0,    91,    2348,    1397),
    (2348,    59,    16,    1412),
    (2348,    59,    16,    1412),
    (74,    61,    8,    15),
    (66,    61,    8,    15),
    (82,    61,    8,    1),
    (82,    62,    1,    13),
    (89,    62,    1,    13),
    (82,    75,    8,    1),
    (83,    62,    6,    13)
    ]
R2 = [
    (1268,    59,    16,    1082),
    (2,    61,    8,    15),
    (0,    59,    1268,    2),
    (0,    61,    2,    15),
    (10,    61,    1258,    15),
    (0,    76,    1268,    1082),
    (98,    661,    8,    15),
    (34,    676,    120,    15),
    (34,    691,    32,    15),
    (74,    691,    8,    15),
    (90,    691,    136,    15),
    (226,    691,    144,    15),
    (370,    691,    8,    15),
    (386,    691,    48,    15),
    (434,    691,    32,    15),
    (466,    691,    8,    15),
    (482,    691,    184,    15),
    (674,    691,    184,    15),
    (866,    691,    48,    15),
    (914,    691,    32,    15),
    (946,    691,    8,    15),
    (34,    706,    40,    15),
    (82,    706,    16,    15),
    (106,    706,    8,    15),
    (122,    706,    144,    15),
    (34,    721,    16,    15),
    (58,    721,    136,    15),
    (194,    721,    8,    15),
    (202,    721,    8,    15),
    (66,    736,    40,    15),
    (106,    736,    8,    15),
    (114,    736,    352,    15),
    (474,    736,    8,    15),
    (490,    736,    128,    15),
    (66,    751,    48,    15),
    (130,    751,    40,    15),
    (34,    766,    16,    15),
    (58,    766,    24,    15),
    (90,    766,    32,    15),
    (66,    781,    40,    15),
    (106,    781,    8,    15),
    (114,    781,    280,    15),
    (394,    781,    8,    15),
    (66,    796,    48,    15),
    (130,    796,    40,    15),
    (34,    811,    24,    15),
    (66,    811,    8,    15),
    (82,    811,    88,    15),
    (170,    811,    56,    15),
    (226,    811,    8,    15),
    (34,    826,    16,    15),
    (58,    826,    40,    15),
    (98,    826,    80,    15),
    (178,    826,    8,    15),
    (66,    841,    40,    15),
    (106,    841,    8,    15),
    (114,    841,    416,    15),
    (530,    841,    8,    15),
    (66,    856,    48,    15),
    (130,    856,    40,    15),
    (34,    871,    24,    15),
    (66,    871,    8,    15),
    (82,    871,    72,    15),
    (154,    871,    24,    15),
    (178,    871,    8,    15),
    (34,    886,    16,    15),
    (58,    886,    40,    15),
    (98,    886,    8,    15),
    (106,    886,    8,    15),
    (66,    901,    24,    15),
    (98,    901,    8,    15),
    (114,    901,    64,    15),
    (178,    901,    8,    15),
    (186,    901,    16,    15),
    (34,    916,    56,    15),
    (98,    916,    8,    15),
    (114,    916,    16,    15),
    (34,    931,    24,    15),
    (66,    931,    8,    15),
    (82,    931,    16,    15),
    (106,    931,    32,    15),
    (66,    946,    16,    15),
    (90,    946,    8,    15),
    (106,    946,    16,    15),
    (130,    946,    96,    15),
    (226,    946,    8,    15),
    (98,    961,    56,    15),
    (162,    961,    16,    15),
    (186,    961,    8,    15),
    (34,    976,    16,    15),
    (58,    976,    24,    15),
    (90,    976,    64,    15),
    (66,    991,    40,    15),
    (106,    991,    8,    15),
    (114,    991,    664,    15),
    (786,    991,    8,    15),
    (802,    991,    72,    15),
    (882,    991,    40,    15),
    (66,    1006,    48,    15),
    (130,    1006,    40,    15),
    (34,    1036,    24,    15),
    (66,    1036,    8,    15),
    (82,    1036,    24,    15),
    (106,    1036,    72,    15),
    (34,    1051,    48,    15),
    (82,    1051,    80,    15),
    (162,    1051,    8,    15),
    (178,    1051,    8,    15),
    (194,    1051,    24,    15),
    (34,    1066,    296,    15),
    (34,    1081,    56,    15),
    (98,    1081,    8,    15),
    (114,    1081,    8,    15),
    (34,    1096,    32,    15),
    (74,    1096,    8,    15),
    (90,    1096,    136,    15),
    (226,    1096,    96,    15),
    (322,    1096,    8,    15),
    (338,    1096,    48,    15),
    (386,    1096,    32,    15),
    (418,    1096,    8,    15),
    (434,    1096,    184,    15),
    (626,    1096,    184,    15),
    (818,    1096,    48,    15),
    (866,    1096,    32,    15),
    (898,    1096,    8,    15),
    (34,    1111,    40,    15),
    (82,    1111,    16,    15),
    (106,    1111,    8,    15),
    (122,    1111,    144,    15),
    (34,    1126,    16,    15),
    (58,    1126,    104,    15),
    (162,    1126,    8,    15),
    (170,    1126,    8,    15),
    (1122,    1141,    40,    15),
    (1234,    1141,    24,    15),
    (1258,    1141,    8,    15),
    (2,    61,    8,    15),
    (1268,    59,    16,    1082),
    (1268,    59,    16,    1082),
    (1268,    59,    16,    1082),
    (2,    61,    8,    15)
    ]

N = 1000

def test_gvim_damage_performance(rectangles):
    start = time.time()
    for _ in range(N):
        rects = []
        for x,y,width,height in rectangles:
            r = rectangle(x, y, width, height)
            rects.append(r)
    end = time.time()
    print("created %s rectangles %s times in %.2fms" % (len(rectangles), N, (end-start)*1000.0/N))
    #now try add rectangle:
    start = time.time()
    for _ in range(N):
        rects = []
        for x,y,width,height in rectangles:
            r = rectangle(x, y, width, height)
            add_rectangle(rects, r)
    end = time.time()
    print("add_rectangle %s rectangles %s times in %.2fms" % (len(rectangles), N, (end-start)*1000.0/N))
    #now try remove rectangle:
    start = time.time()
    for _ in range(N):
        rects = []
        for x,y,width,height in rectangles:
            r = rectangle(x+width//4, y+height//3, width//2, height//2)
            remove_rectangle(rects, r)
    end = time.time()
    print("remove_rectangle %s rectangles %s times in %.2fms" % (len(rectangles), N, (end-start)*1000.0/N))

    start = time.time()
    n = N*1000
    for _ in range(n):
        for r in rects:
            contains_rect(rects, r)
    end = time.time()
    print("contains_rect %s rectangles %s times in %.2fms" % (len(rectangles), n, (end-start)*1000.0/N))


def test_merge_all():
    start = time.time()
    R = [rectangle(*v) for v in R1+R2]
    n = N*10
    for _ in range(n):
        v = merge_all(R)
    end = time.time()
    print("merged %s rectangles %s times in %.2fms" % (len(R), n, (end-start)*1000.0/N))


def main():
    print("R1:")
    test_gvim_damage_performance(R1)
    print("")
    print("R2:")
    test_gvim_damage_performance(R2)

    print("")
    test_merge_all()

if __name__ == "__main__":
    main()
