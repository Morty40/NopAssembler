#! /usr/bin/env python3
"""Tests of the text encodings."""

import unittest

from ..text import (
    chr,
    ENCODING_PETSCII_MIXED,
    ENCODING_PETSCII_UPPER,
    ENCODING_SCREEN_MIXED,
    ENCODING_SCREEN_UPPER,
    ord,
)


class TestText(unittest.TestCase):
    """The encoding tables, and chr() and ord() in each encoding."""

    def testOrdReversesChr(self):
        """In every encoding, ord gives the value of every character, and chr gives the character back."""
        for encoding in [ENCODING_SCREEN_UPPER, ENCODING_SCREEN_MIXED, ENCODING_PETSCII_UPPER, ENCODING_PETSCII_MIXED]:
            for char, value in encoding.items():
                with self.subTest(char=char, value=value):
                    self.assertEqual(ord(char, encoding), value)
                    self.assertEqual(chr(value, encoding), char)

    def testUnknown(self):
        """A value or character that is not in the encoding gives None."""
        self.assertEqual(chr(255, ENCODING_SCREEN_UPPER), None)
        self.assertEqual(ord('€', ENCODING_PETSCII_MIXED), None)

    def testFirstCharacter(self):
        """If two characters have the same value, chr gives the first of them."""
        self.assertEqual(chr(1, {'A': 1, 'a': 1}), 'A')

    def testApostrophe(self):
        """The apostrophe is code 39 in every encoding."""
        for encoding in [ENCODING_SCREEN_UPPER, ENCODING_SCREEN_MIXED, ENCODING_PETSCII_UPPER, ENCODING_PETSCII_MIXED]:
            self.assertEqual(ord("'", encoding), 39)

    def testGraphics(self):
        """Pi and the card suits are in the upper case encodings, where the mixed case ones have letters."""
        for char, screenCode, petscii in [('♠', 65, 97), ('♥', 83, 115), ('♣', 88, 120), ('♦', 90, 122), ('π', 94, 126)]:
            with self.subTest(char=char):
                self.assertEqual(ord(char, ENCODING_SCREEN_UPPER), screenCode)
                self.assertEqual(ord(char, ENCODING_PETSCII_UPPER), petscii)
                self.assertEqual(ord(char, ENCODING_SCREEN_MIXED), None)
                self.assertEqual(ord(char, ENCODING_PETSCII_MIXED), None)

    def testLetters(self):
        """The codes of A and a in each encoding. The upper case encodings have no lower case letters."""
        for encoding, upper, lower in [(ENCODING_SCREEN_UPPER,  1,  None),
                                       (ENCODING_SCREEN_MIXED,  65, 1),
                                       (ENCODING_PETSCII_UPPER, 65, None),
                                       (ENCODING_PETSCII_MIXED, 97, 65)]:
            with self.subTest(encoding=encoding):
                self.assertEqual(ord('A', encoding), upper)
                self.assertEqual(chr(upper, encoding), 'A')
                self.assertEqual(ord('a', encoding), lower)
                if lower is not None:
                    self.assertEqual(chr(lower, encoding), 'a')


if __name__ == '__main__':
    unittest.main()
