# This file is part of Parti.
# Copyright (C) 2008 Nathaniel Smith <njs@pobox.com>
# Copyright (C) 2011, 2012 Antoine Martin <antoine@nagafix.co.uk>
# Parti is released under the terms of the GNU GPL v2, or, at your option, any
# later version. See the file COPYING for details.

def mask_to_names(mask, modifier_map):
    modifiers = []
    for modifier in DEFAULT_ALL_MODIFIER_NAMES:
        modifier_mask = modifier_map.get(modifier)
        if (modifier_mask is not None) and (modifier_mask & mask):
            modifiers.append(modifier)
            mask &= ~modifier_mask
    return modifiers

def nn(x):
    if x is None:
        return ""
    return x

def get_gtk_keymap(ignore_keys=[None, "VoidSymbol"], add_if_missing=[]):
    """
        Augment the keymap we get from gtk.gdk.keymap_get_default()
        by adding the keyval_name.
        We can also ignore some keys
    """
    import pygtk
    pygtk.require("2.0")
    import gtk
    keymap = gtk.gdk.keymap_get_default()
    keycodes=[]
    max_entries = 1
    for i in range(0, 2**8):
        entries = keymap.get_entries_for_keycode(i)
        if entries:
            max_entries = max(max_entries, len(entries))
            for keyval, keycode, group, level in entries:
                name = gtk.gdk.keyval_name(keyval)
                if name not in ignore_keys:
                    keycodes.append((nn(keyval), nn(name), nn(keycode), nn(group), nn(level)))
                if name in add_if_missing:
                    add_if_missing.remove(name)
    #TODO: do this server-side to ensure all modifiers can be set
    if add_if_missing:
        for name in add_if_missing:
            keycodes.append((0, name, 0, 0, 0))
    return keycodes



DEFAULT_MODIFIER_IGNORE_KEYNAMES = ["Caps_Lock", "Num_Lock", "Scroll_Lock"]

ALL_X11_MODIFIERS = {
                    "shift"     : 0,
                    "lock"      : 1,
                    "control"   : 2,
                    "mod1"      : 3,
                    "mod2"      : 4,
                    "mod3"      : 5,
                    "mod4"      : 6,
                    "mod5"      : 7
                    }

DEFAULT_MODIFIER_NAMES = ["shift", "control", "meta", "super", "hyper", "alt"]
DEFAULT_MODIFIER_NUISANCE = ["lock", "num", "scroll"]
DEFAULT_ALL_MODIFIER_NAMES = DEFAULT_MODIFIER_NAMES+DEFAULT_MODIFIER_NUISANCE+["mod1", "mod2", "mod3", "mod4", "mod5"]

XMODMAP_MOD_CLEAR = ["clear Lock", "clear Shift", "clear Control",
                 "clear Mod1", "clear Mod2", "clear Mod3", "clear Mod4", "clear Mod5"]
XMODMAP_MOD_ADD = ["add Lock = Caps_Lock",
                 "add Shift = Shift_L Shift_R",
                 "add Control = Control_L Control_R",
                 "add Mod1 = Meta_L Meta_R",
                 "add Mod2 = Num_Lock",
                 "add Mod3 = Hyper_L Hyper_R",
                 "add Mod4 = Super_L Super_R",
                 "add Mod5 = Alt_L Alt_R"]

XMODMAP_MOD_DEFAULTS = ["keycode any = Shift_L",
                   "keycode any = Shift_R",
                   "keycode any = Control_L",
                   "keycode any = Control_R",
                   "keycode any = Meta_L",
                   "keycode any = Meta_R",
                   "keycode any = Alt_L",
                   "keycode any = Alt_R",
                   "keycode any = Hyper_L",
                   "keycode any = Hyper_R",
                   "keycode any = Super_L",
                   "keycode any = Super_R",
                   "keycode any = Num_Lock",
                    # Really stupid hack to force backspace to work.
                   "keycode any = BackSpace"]

DEFAULT_MODIFIER_MEANINGS = {
        "Shift_L"   : "shift",
        "Shift_R"   : "shift",
        "Caps_Lock" : "lock",
        "Control_L" : "control",
        "Control_R" : "control",
        "Alt_L"     : "mod1",
        "Alt_R"     : "mod1",
        "Num_Lock"  : "mod2",
        "Meta_L"    : "mod3",
        "Meta_R"    : "mod3",
        "Super_L"   : "mod4",
        "Super_R"   : "mod4",
        "Hyper_L"   : "mod4",
        "Hyper_R"   : "mod4",
        "ISO_Level3_Shift"  : "mod5",
        "Mode_switch"       : "mod5",
        }

DEFAULT_KEYNAME_FOR_MOD = {
            "shift": ["Shift_L", "Shift_R"],
            "control": ["Control_L", "Control_R"],
            "meta": ["Meta_L", "Meta_R"],
            "super": ["Super_L", "Super_R"],
            "hyper": ["Hyper_L", "Hyper_R"],
            "alt": ["Alt_L", "Alt_R"],
            "lock": ["Caps_Lock"],
            "num": ["Num_Lock"],
            }
