"""Apple virtual key codes -> stable core IDs (physical US QWERTY positions).

Caps Lock and the previously active keyboard layout do not change 두벌식.
Shift is supplied independently by NSEvent.
"""

from korkana import keys

_LETTERS = {
    0: "A", 1: "S", 2: "D", 3: "F", 4: "H", 5: "G", 6: "Z", 7: "X",
    8: "C", 9: "V", 11: "B", 12: "Q", 13: "W", 14: "E", 15: "R",
    16: "Y", 17: "T", 31: "O", 32: "U", 34: "I", 35: "P", 37: "L",
    38: "J", 40: "K", 45: "N", 46: "M",
}
_PRINTABLE = {
    18: "1!", 19: "2@", 20: "3#", 21: "4$", 22: "6^", 23: "5%",
    24: "=+", 25: "9(", 26: "7&", 27: "-_", 28: "8*", 29: "0)",
    30: "]}", 33: "[{", 39: "'\"", 41: ";:", 42: "\\|", 43: ",<",
    44: "/?", 47: ".>", 49: "  ", 50: "`~",
}
_SPECIAL = {
    36: keys.VK_RETURN, 48: keys.VK_TAB, 51: keys.VK_BACK,
    53: keys.VK_ESCAPE, 76: keys.VK_RETURN,
    123: 0x25, 124: 0x27, 125: 0x28, 126: 0x26,
    115: 0x24, 119: 0x23, 116: 0x21, 121: 0x22, 117: 0x2E,
}
_KEYPAD = {65: ".", 67: "*", 69: "+", 75: "/", 78: "-", 81: "=",
           82: "0", 83: "1", 84: "2", 85: "3", 86: "4", 87: "5",
           88: "6", 89: "7", 91: "8", 92: "9"}


def translate(keycode, shift=False):
    if keycode in _LETTERS:
        letter = _LETTERS[keycode]
        return ord(letter), letter if shift else letter.lower()
    if keycode in _PRINTABLE:
        pair = _PRINTABLE[keycode]
        return keys.from_character(pair[0]), pair[int(shift)]
    if keycode in _KEYPAD:
        # Numpad text is literal, including decimal and minus.
        return 0x60 + "0123456789*/+-=.".index(_KEYPAD[keycode]), _KEYPAD[keycode]
    return _SPECIAL.get(keycode, 0), ""
