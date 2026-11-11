#! /usr/bin/env python3
"""Tests of the BASIC versions."""

import unittest

from ..basic import BASIC_1, BASIC_2, BASIC_3_5, BASIC_4, BASIC_4_PLUS, BASIC_7


class TestBasic(unittest.TestCase):
    """Tests of the keywords and tokens of each BASIC version."""

    def testTokens(self):
        """The BASIC_TOKEN_ symbols, named after the keywords, and the pi character."""
        tokens = BASIC_2.tokens()
        self.assertEqual(len(tokens), 77)                              # 76 keywords and pi
        for name, value in {'END': 0x80, 'INPUT_FILE': 0x84, 'INPUT': 0x85, 'REM': 0x8f, 'PRINT_FILE': 0x98, 'PRINT': 0x99,
                            'SYS': 0x9e, 'TAB': 0xa3, 'PLUS': 0xaa, 'LESS': 0xb3, 'CHR': 0xc7, 'GO': 0xcb, 'PI': 0xff}.items():
            with self.subTest(name=name):
                self.assertEqual(tokens[f'BASIC_TOKEN_{name}'], value)

    def testEncode(self):
        """Keywords become tokens, except in strings, after REM, and in DATA, and the rest stays as text."""
        def code(*values):
            """The bytes of the values: a token, or text."""
            return [b for value in values for b in ([value] if type(value) is int else value.encode('ascii'))]
        for text, expected in [
            ('SYS 2061',              code(0x9e, ' 2061')),
            ('POKE 53280,0:SYS 2061', code(0x97, ' 53280,0:', 0x9e, ' 2061')),
            ('poke 1,2',              code(0x97, ' 1,2')),
            ('GOTO 10',               code(0x89, ' 10')),              # not GO and TO
            ('INPUT#1,A',             code(0x84, '1,A')),              # not INPUT and #
            ('PRINT#1',               code(0x98, '1')),
            ('A=1+2',                 code('A', 0xb2, '1', 0xaa, '2')),
            ('FOR I=1 TO 3',          code(0x81, ' I', 0xb2, '1 ', 0xa4, ' 3')),
            ('PRINT CHR$(147)',       code(0x99, ' ', 0xc7, '(147)')),
            ('PRINT "POKE":SYS 1',    code(0x99, ' "POKE":', 0x9e, ' 1')),
            ('REM POKE:SYS "X',       code(0x8f, ' POKE:SYS "X')),
            ('DATA POKE,"A:B":SYS 1', code(0x83, ' POKE,"A:B":', 0x9e, ' 1')),
            ('?"HI":?A',              code(0x99, '"HI":', 0x99, 'A')), # ? is short for PRINT
            ('?"?":DATA ?:REM ?',     code(0x99, '"?":', 0x83, ' ?:', 0x8f, ' ?')), # but not in strings, DATA and REM
            ('PRINT π:PRINT "π":REM π', code(0x99, ' ', 0xff, ':', 0x99, ' "', 0xff, '":', 0x8f, ' ', 0xff)), # pi, anywhere
            ('',                      []),
        ]:
            with self.subTest(text=text):
                self.assertEqual(BASIC_2.encode(text), expected)

    def testBasic1(self):
        """BASIC 1.0 has the keywords of BASIC 2.0, except GO."""
        tokens = BASIC_1.tokens()
        self.assertEqual(len(tokens), 76)                              # 75 keywords and pi
        self.assertNotIn('BASIC_TOKEN_GO', tokens)
        self.assertEqual((tokens['BASIC_TOKEN_GOTO'], tokens['BASIC_TOKEN_MID']), (0x89, 0xca))
        self.assertEqual(BASIC_1.encode('GO TO 10'), [*b'GO ', 0xa4, *b' 10'])
        self.assertEqual(BASIC_2.encode('GO TO 10'), [0xcb, ord(' '), 0xa4, *b' 10'])

    def testBasic4(self):
        """BASIC 4.0 adds disk keywords with tokens from $cc, other values than in BASIC 3.5."""
        tokens = BASIC_4.tokens()
        self.assertEqual(len(tokens), 92)                              # 91 keywords and pi
        self.assertEqual((tokens['BASIC_TOKEN_GO'], tokens['BASIC_TOKEN_CONCAT'], tokens['BASIC_TOKEN_DLOAD'], tokens['BASIC_TOKEN_DIRECTORY']),
                         (0xcb, 0xcc, 0xd6, 0xda))
        self.assertEqual(BASIC_4.encode('DLOAD"X":SYS 1'), [0xd6, *b'"X":', 0x9e, *b' 1'])
        self.assertEqual(BASIC_3_5.encode('DLOAD"X"'), [0xf0, *b'"X"'])

    def testBasic4Plus(self):
        """BASIC 4.0+ adds keywords to BASIC 4.0, with tokens from $db, other values than in BASIC 3.5."""
        tokens = BASIC_4_PLUS.tokens()
        self.assertEqual(len(tokens), 106)                             # 105 keywords and pi
        self.assertEqual((tokens['BASIC_TOKEN_DIRECTORY'], tokens['BASIC_TOKEN_DCLEAR'], tokens['BASIC_TOKEN_ELSE'], tokens['BASIC_TOKEN_INSTR']),
                         (0xda, 0xdb, 0xe1, 0xe8))
        self.assertEqual(BASIC_4_PLUS.encode('IF A THEN 10:ELSE 20'), [0x8b, *b' A ', 0xa7, *b' 10:', 0xe1, *b' 20'])
        self.assertEqual(BASIC_3_5.encode('ELSE'), [0xd5])

    def testBasic35(self):
        """BASIC 3.5 adds keywords with tokens from $cc, which are text in BASIC 2.0."""
        tokens = BASIC_3_5.tokens()
        self.assertEqual(len(tokens), 127)                             # 126 keywords and pi
        self.assertEqual((tokens['BASIC_TOKEN_GO'], tokens['BASIC_TOKEN_RGR'], tokens['BASIC_TOKEN_HEX'], tokens['BASIC_TOKEN_WHILE']),
                         (0xcb, 0xcc, 0xd2, 0xfd))
        self.assertEqual(BASIC_3_5.encode('GRAPHIC 1:SYS 1'), [0xde, *b' 1:', 0x9e, *b' 1'])
        self.assertEqual(BASIC_2.encode('GRAPHIC 1'), list(b'GRAPHIC 1'))

    def testBasic7(self):
        """BASIC 7.0 has the keywords of BASIC 3.5, except RLUM, and keywords with two-byte tokens."""
        tokens = BASIC_7.tokens()
        self.assertEqual(len(tokens), 126)                             # 125 keywords with one-byte tokens, and pi
        self.assertNotIn('BASIC_TOKEN_RLUM', tokens)                   # $ce is a prefix
        self.assertEqual((tokens['BASIC_TOKEN_JOY'], tokens['BASIC_TOKEN_WHILE']), (0xcf, 0xfd))
        for text, expected in [
            ('BANK 15',          [0xfe, 0x02, *b' 15']),
            ('SWAP:FAST:SLOW',   [0xfe, 0x23, ord(':'), 0xfe, 0x25, ord(':'), 0xfe, 0x26]), # after the unused tokens
            ('DOPEN#1,"X"',      [0xfe, 0x0d, *b'#1,"X"']),            # not DO and PEN
            ('PRINT POT(1)',     [0x99, ord(' '), 0xce, 0x02, *b'(1)']),
            ('A=1 XOR 2',        [ord('A'), 0xb2, *b'1 ', 0xce, 0x08, *b' 2']),
            ('GRAPHIC 1',        [0xde, *b' 1']),
            ('RLUM',             list(b'RLUM')),
        ]:
            with self.subTest(text=text):
                self.assertEqual(BASIC_7.encode(text), expected)

    def testEncodeError(self):
        """Text that BASIC can't store is an error."""
        with self.assertRaises(UnicodeEncodeError):
            BASIC_2.encode('PRINT "é"')


if __name__ == '__main__':
    unittest.main()
