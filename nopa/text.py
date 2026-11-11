#! /usr/bin/env python3
"""Text encodings: screen codes and PETSCII, in upper case and mixed case.

Screen codes are the values stored in screen memory, and PETSCII the values
printed by the KERNAL. Each comes in two versions, one for each of the C64's
character sets: upper case with graphics, and mixed lower and upper case.

The tables cover letters, digits, punctuation, and in the upper case
encodings pi and the card suits. Other values and characters
are not in an encoding, and chr() and ord() return None for them.
"""


# screen codes, upper case with graphics: A-Z at 1-26, card suits and pi at 65-94
_chrScreenUpper = {
    0x00: '@', 0x01: 'A', 0x02: 'B', 0x03: 'C', 0x04: 'D', 0x05: 'E', 0x06: 'F', 0x07: 'G',
    0x08: 'H', 0x09: 'I', 0x0a: 'J', 0x0b: 'K', 0x0c: 'L', 0x0d: 'M', 0x0e: 'N', 0x0f: 'O',
    0x10: 'P', 0x11: 'Q', 0x12: 'R', 0x13: 'S', 0x14: 'T', 0x15: 'U', 0x16: 'V', 0x17: 'W',
    0x18: 'X', 0x19: 'Y', 0x1a: 'Z', 0x1b: '[', 0x1c: '£', 0x1d: ']', 0x1e: '↑', 0x1f: '←',
    0x20: ' ', 0x21: '!', 0x22: '"', 0x23: '#', 0x24: '$', 0x25: '%', 0x26: '&', 0x27: "'",
    0x28: '(', 0x29: ')', 0x2a: '*', 0x2b: '+', 0x2c: ',', 0x2d: '-', 0x2e: '.', 0x2f: '/',
    0x30: '0', 0x31: '1', 0x32: '2', 0x33: '3', 0x34: '4', 0x35: '5', 0x36: '6', 0x37: '7',
    0x38: '8', 0x39: '9', 0x3a: ':', 0x3b: ';', 0x3c: '<', 0x3d: '=', 0x3e: '>', 0x3f: '?',
    0x41: '♠', 0x53: '♥', 0x58: '♣', 0x5a: '♦', 0x5e: 'π',
}

# screen codes, mixed case: a-z at 1-26, A-Z at 65-90
_chrScreenMixed = {
    0x00: '@', 0x01: 'a', 0x02: 'b', 0x03: 'c', 0x04: 'd', 0x05: 'e', 0x06: 'f', 0x07: 'g',
    0x08: 'h', 0x09: 'i', 0x0a: 'j', 0x0b: 'k', 0x0c: 'l', 0x0d: 'm', 0x0e: 'n', 0x0f: 'o',
    0x10: 'p', 0x11: 'q', 0x12: 'r', 0x13: 's', 0x14: 't', 0x15: 'u', 0x16: 'v', 0x17: 'w',
    0x18: 'x', 0x19: 'y', 0x1a: 'z', 0x1b: '[', 0x1c: '£', 0x1d: ']', 0x1e: '↑', 0x1f: '←',
    0x20: ' ', 0x21: '!', 0x22: '"', 0x23: '#', 0x24: '$', 0x25: '%', 0x26: '&', 0x27: "'",
    0x28: '(', 0x29: ')', 0x2a: '*', 0x2b: '+', 0x2c: ',', 0x2d: '-', 0x2e: '.', 0x2f: '/',
    0x30: '0', 0x31: '1', 0x32: '2', 0x33: '3', 0x34: '4', 0x35: '5', 0x36: '6', 0x37: '7',
    0x38: '8', 0x39: '9', 0x3a: ':', 0x3b: ';', 0x3c: '<', 0x3d: '=', 0x3e: '>', 0x3f: '?',
    0x40: '―', 0x41: 'A', 0x42: 'B', 0x43: 'C', 0x44: 'D', 0x45: 'E', 0x46: 'F', 0x47: 'G',
    0x48: 'H', 0x49: 'I', 0x4a: 'J', 0x4b: 'K', 0x4c: 'L', 0x4d: 'M', 0x4e: 'N', 0x4f: 'O',
    0x50: 'P', 0x51: 'Q', 0x52: 'R', 0x53: 'S', 0x54: 'T', 0x55: 'U', 0x56: 'V', 0x57: 'W',
    0x58: 'X', 0x59: 'Y', 0x5a: 'Z',
}

# PETSCII, upper case with graphics: A-Z at 65-90, card suits and pi at 97-126
_chrPetsciiUpper = {
    32: ' ', 33: '!', 34: '"', 35: '#', 36: '$', 37: '%', 38: '&', 39: "'",
    40: '(', 41: ')', 42: '*', 43: '+', 44: ',', 45: '-', 46: '.', 47: '/',
    48: '0', 49: '1', 50: '2', 51: '3', 52: '4', 53: '5', 54: '6', 55: '7',
    56: '8', 57: '9', 58: ':', 59: ';', 60: '<', 61: '=', 62: '>', 63: '?',
    64: '@', 65: 'A', 66: 'B', 67: 'C', 68: 'D', 69: 'E', 70: 'F', 71: 'G',
    72: 'H', 73: 'I', 74: 'J', 75: 'K', 76: 'L', 77: 'M', 78: 'N', 79: 'O',
    80: 'P', 81: 'Q', 82: 'R', 83: 'S', 84: 'T', 85: 'U', 86: 'V', 87: 'W',
    88: 'X', 89: 'Y', 90: 'Z', 91: '[', 92: '£', 93: ']', 94: '↑', 95: '←',
    97: '♠', 115: '♥', 120: '♣', 122: '♦', 126: 'π',
}

# PETSCII, mixed case: a-z at 65-90, A-Z at 97-122
_chrPetsciiMixed = {
    32: ' ', 33: '!', 34: '"', 35: '#', 36: '$', 37: '%', 38: '&', 39: "'",
    40: '(', 41: ')', 42: '*', 43: '+', 44: ',', 45: '-', 46: '.', 47: '/',
    48: '0', 49: '1', 50: '2', 51: '3', 52: '4', 53: '5', 54: '6', 55: '7',
    56: '8', 57: '9', 58: ':', 59: ';', 60: '<', 61: '=', 62: '>', 63: '?',
    64: '@', 65: 'a', 66: 'b', 67: 'c', 68: 'd', 69: 'e', 70: 'f', 71: 'g',
    72: 'h', 73: 'i', 74: 'j', 75: 'k', 76: 'l', 77: 'm', 78: 'n', 79: 'o',
    80: 'p', 81: 'q', 82: 'r', 83: 's', 84: 't', 85: 'u', 86: 'v', 87: 'w',
    88: 'x', 89: 'y', 90: 'z', 91: '[', 92: '£', 93: ']', 94: '↑', 95: '←',
    96: '―', 97: 'A', 98: 'B', 99: 'C',100: 'D',101: 'E',102: 'F',103: 'G',
   104: 'H',105: 'I',106: 'J',107: 'K',108: 'L',109: 'M',110: 'N',111: 'O',
   112: 'P',113: 'Q',114: 'R',115: 'S',116: 'T',117: 'U',118: 'V',119: 'W',
   120: 'X',121: 'Y',122: 'Z',
}


def _encoding(table: dict[int, str]) -> dict[str, int]:
    """An encoding is a table of characters and their values: the reverse of a table above."""
    return {char: value for value, char in table.items()}


# the encodings, as used by .encoding, e.g. .encoding ENCODING_PETSCII_UPPER
ENCODING_SCREEN_UPPER = _encoding(_chrScreenUpper)
ENCODING_SCREEN_MIXED = _encoding(_chrScreenMixed)
ENCODING_PETSCII_UPPER = _encoding(_chrPetsciiUpper)
ENCODING_PETSCII_MIXED = _encoding(_chrPetsciiMixed)


def chr(value: int, encoding: dict[str, int]) -> str | None:
    """Return the first character with a value in the encoding, or None if there is none."""
    return next((char for char, v in encoding.items() if v == value), None)


def ord(char: str, encoding: dict[str, int]) -> int | None:
    """Return the value of a character in the encoding, or None if it has none."""
    return encoding.get(char)
