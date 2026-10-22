"""Stable internal key IDs; Windows VK values retained for compatibility.

Native adapters translate their own key events into these IDs. No OS APIs here.
"""

VK_BACK, VK_TAB, VK_RETURN = 0x08, 0x09, 0x0D
VK_ESCAPE, VK_SPACE = 0x1B, 0x20
VK_A, VK_Z = 0x41, 0x5A
VK_OEM_MINUS = 0xBD

# Printable US keyboard positions, unshifted and shifted.
_BASE = "0123456789;=,-./`[\\]'"
_SHIFT = ")!@#$%^&*(:+<_>?~{|}\""
_CODES = [*range(0x30, 0x3A), 0xBA, 0xBB, 0xBC, 0xBD, 0xBE,
          0xBF, 0xC0, 0xDB, 0xDC, 0xDD, 0xDE]
CHAR_KEYS = dict(zip(_BASE, _CODES))
CHAR_KEYS.update(zip(_SHIFT, _CODES))
SPECIAL_KEYS = {"BackSpace": VK_BACK, "Tab": VK_TAB, "Return": VK_RETURN,
                "Escape": VK_ESCAPE, "space": VK_SPACE,
                "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28,
                "Delete": 0x2E, "Home": 0x24, "End": 0x23,
                "Page_Up": 0x21, "Page_Down": 0x22}


def from_character(text: str) -> int:
    if len(text) != 1:
        return 0
    if text.isascii() and text.isalpha():
        return ord(text.upper())
    if text == " ":
        return VK_SPACE
    return CHAR_KEYS.get(text, 0)
