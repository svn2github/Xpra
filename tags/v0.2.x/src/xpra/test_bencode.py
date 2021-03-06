# This file is part of Parti.
# Copyright (C) 2011, 2012 Antoine Martin <antoine@devloop.org.uk>
# Parti is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

from xpra.bencode import IncrBDecode, bencode

    
def process(input):
    bd = IncrBDecode()
    bd.add(input)
    return  bd.process()

def test_decoding():
    
    def t(str, value, remainder):
        print(str)
        # Test "one-shot":
        assert process(str) == (value, remainder)
        # With gibberish added:
        assert process(str + "asdf") == (value, remainder + "asdf")
        # Byte at a time:
        decoder = IncrBDecode()
        for i, c in enumerate(str):
            decoder.add(c)
            retval = decoder.process()
            if retval is not None:
                print(retval)
                assert retval == (value, "")
                assert str[i + 1:] == remainder
                break

    t("i12345e", 12345, "")
    t("i-12345e", -12345, "")
    t("i12345eQQQ", 12345, "QQQ")
    t("3:foo", "foo", "")
    t("3:fooQQQ", "foo", "QQQ")
    t("li12e4:asdfi34ee", [12, "asdf", 34], "")
    t("d4:asdf3:foo4:bsdfi1234ee", {"asdf": "foo", "bsdf": 1234}, "")

    t("d4:asdfli1ei2ei3ei4ee5:otheri-55e2:qqd2:qql2:hieee",
      {"asdf": [1, 2, 3, 4], "qq": {"qq": ["hi"]}, "other": -55},
      "")

    t("l0:e", [""], "")

    print("------")
    def te(str, exc):
        print(str)
        try:
            process(str)
        except exc:
            pass
        else:
            assert False, "didn't raise exception"
        try:
            decoder = IncrBDecode()
            for c in str:
                decoder.add(c)
                decoder.process()
        except exc:
            pass
        else:
            assert False, "didn't raise exception"

    te("iie", ValueError)
    te("i0x0e", ValueError)
    t("i0e", 0, "")
    te("i00e", ValueError)

    te("0x2:aa", ValueError)
    te("-1:aa", ValueError)
    te("02:aa", ValueError)

    # Keys must be strings:
    te("di0ei0ee", ValueError)
    te("dli0eei0ee", ValueError)
    te("dd1:a1:aei0ee", ValueError)
    # Keys must be in ascending order:
    te("d1:bi0e1:ai0e1:ci0ee", ValueError)
    te("d1:ai0e1:ci0e1:bi0ee", ValueError)

    te("l5:hellod20:__prerelease_version8:0.0.7.2612:desktop_sizeli480ei800ee4:jpegi40e18:challenge_response40:ba59e4110119264f4a6eaf3adc075ea2c5408550ee", ValueError)
    #no idea why this does not fail if the one above does!:
    #te("l5:hellod20:__prerelease_version8:0.0.7.2618:challenge_response40:ba59e4110119264f4a6eaf3adc075ea2c540855012:desktop_sizeli480ei800ee4:jpegi40eee", ValueError)


def test_encoding():

    def t(v, encstr=None):
        be = bencode(v)
        print("bencode(%s)=%s" % (v, be))
        if encstr:
            assert be==encstr
        restored = process(be)
        print("decode(%s)=%s" % (be, restored))
        list = restored[0]
        if len(list)!=len(v):
            print("MISMATCH!")
            print("v=%s" % v)
            print("l=%s" % list)
        assert len(list)==2
        assert list[0]==v[0]
        for ok,ov in v[1].items():
            d = list[1]
            if ok not in d:
                print("restored dict is missing %s" % ok)
                return list
            rv = d.get(ok)
            if rv!=ov:
                print("value for %s does not match: %s vs %s" % (ok, ov, rv))
                return list
                
        return list

    def test_hello():
        d = {}
        d["__prerelease_version"] = "0.0.7.26"
        #caps.put("deflate", 6);
        d["desktop_size"] = [480,800]
        jpeg = 4
        d["jpeg"] =  jpeg
        challenge = "ba59e4110119264f4a6eaf3adc075ea2c5408550"
        d["challenge_response"] = challenge
        hello = ["hello", d]
        t(hello, "l5:hellod20:__prerelease_version8:0.0.7.2618:challenge_response40:ba59e4110119264f4a6eaf3adc075ea2c540855012:desktop_sizeli480ei800ee4:jpegi4eee")

    def test_large_hello():
        d = {'start_time': 1325786122,
                'resize_screen': False, 'bell': True, 'desktop_size': [800, 600], 'modifiers_nuisance': True,
                'actual_desktop_size': [3840, 2560], 'encodings': ['rgb24', 'jpeg', 'png'],
                'ping': True, 'damage_sequence': True, 'packet_size': True,
                'encoding': 'rgb24', 'platform': 'linux2', 'clipboard': True, 'cursors': True,
                'raw_keycodes_feature': True, 'focus_modifiers_feature': True, '__prerelease_version': '0.0.7.33',
                'notifications': True, 'png_window_icons': True,
                }
        hello = ["hello", d]
        t(hello, "l5:hellod20:__prerelease_version8:0.0.7.3319:actual_desktop_sizeli3840ei2560ee4:belli1e9:clipboardi1e7:cursorsi1e15:damage_sequencei1e12:desktop_sizeli800ei600ee8:encoding5:rgb249:encodingsl5:rgb244:jpeg3:pnge23:focus_modifiers_featurei1e18:modifiers_nuisancei1e13:notificationsi1e11:packet_sizei1e4:pingi1e8:platform6:linux216:png_window_iconsi1e20:raw_keycodes_featurei1e13:resize_screeni0e10:start_timei1325786122eee")

        d['some_new_feature_we_may_add'] = {"with_a_nested_dict" : {"containing_another_dict" : ["with", "nested", "arrays", ["in", ["it"]]]}}
        t(hello, "l5:hellod20:__prerelease_version8:0.0.7.3319:actual_desktop_sizeli3840ei2560ee4:belli1e9:clipboardi1e7:cursorsi1e15:damage_sequencei1e12:desktop_sizeli800ei600ee8:encoding5:rgb249:encodingsl5:rgb244:jpeg3:pnge23:focus_modifiers_featurei1e18:modifiers_nuisancei1e13:notificationsi1e11:packet_sizei1e4:pingi1e8:platform6:linux216:png_window_iconsi1e20:raw_keycodes_featurei1e13:resize_screeni0e27:some_new_feature_we_may_addd18:with_a_nested_dictd23:containing_another_dictl4:with6:nested6:arraysl2:inl2:iteeeee10:start_timei1325786122eee")

    test_hello()
    test_large_hello()

def main():
    test_decoding()
    test_encoding()


if __name__ == "__main__":
    main()
