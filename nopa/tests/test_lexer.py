#! /usr/bin/env python3
"""Tests of the lexer."""

import os
import unittest

from ..lexer import (
    _fixPrefix,
    join,
    splitByComma,
    splitByNewline,
    Token,
    tokenize,
    tokenizeFile,
    translateLocalLabels,
)


class TestLexer(unittest.TestCase):
    """Tests of tokenizing source code."""

    def testFixPrefix(self):
        """The number prefixes $ and % become Python's 0x and 0b."""
        self.assertEqual(_fixPrefix(''), '')
        self.assertEqual(_fixPrefix('abc'), 'abc')
        self.assertEqual(_fixPrefix('$1234'), '0x1234')
        self.assertEqual(_fixPrefix('%010101'), '0b010101')
        self.assertEqual(_fixPrefix('%'), '%') # modulo operator, not a binary prefix

    def testModulo(self):
        """% is modulo after a number, name or closing bracket, and otherwise a binary prefix."""
        def strings(line):
            """The tokens of a line as strings, without the newline."""
            return [t.string for t in tokenize(line) if t.string != '\n']
        self.assertEqual(strings('7 % 4'),        ['7', '%', '4'])
        self.assertEqual(strings('7%4'),          ['7', '%', '4'])
        self.assertEqual(strings('10 %4'),        ['10', '%', '4'])
        self.assertEqual(strings('x % 2'),        ['x', '%', '2'])
        self.assertEqual(strings('6 % %11'),      ['6', '%', '0b11'])
        self.assertEqual(strings('%101 % 3'),     ['0b101', '%', '3'])
        self.assertEqual(strings('(%101) % 3'),   ['(', '0b101', ')', '%', '3'])
        self.assertEqual(strings('7 %11'),        ['7', '%11'])
        self.assertEqual(strings('x %10'),        ['x', '%10'])
        self.assertEqual(strings('(5) %10'),      ['(', '5', ')', '%10'])
        self.assertEqual(strings('"%d" %10'),     ['f"%d"', '%10'])
        self.assertEqual(strings('True %10'),     ['True', '%10'])
        # binary prefix after directive, mnemonic and operators
        self.assertEqual(strings('.byte %11'),    ['.', 'byte', '0b11'])
        self.assertEqual(strings('1 if %1 else %10'), ['1', 'if', '0b1', 'else', '0b10'])
        self.assertEqual(strings('not %1'),       ['not', '0b1'])
        self.assertEqual(strings('.byte 1, %11'), ['.', 'byte', '1', ',', '0b11'])
        self.assertEqual(strings('lda %11'),      ['lda', '0b11'])
        self.assertEqual(strings('stz %11'),      ['stz', '0b11'])   # a 65C02 mnemonic
        self.assertEqual(strings('lda #%11'),     ['lda', '#', '0b11'])
        self.assertEqual(strings('x = %11'),      ['x', '=', '0b11'])

    def testTokenRepr(self):
        """A token is shown with its file and line."""
        self.assertEqual(repr(Token('lda', 'a.asm', 3)), 'lda (a.asm:3)')
        self.assertEqual(repr(Token('\n')), '\\n (:0)') # newline is shown escaped

    def testUnclosedQuote(self):
        """A missing end quote doesn't crash, and the other lines are still tokenized."""
        strings = [t.string for t in tokenize('nop\n.text "abc\nrts')]
        self.assertEqual(strings[:2], ['nop', '\n'])
        self.assertEqual(strings[-2:], ['rts', '\n'])

    def testSplitByComma(self):
        """Tokens are split at the commas that are not inside brackets."""
        parts = splitByComma(tokenize('a=0, a<len([1, 2]), {"x": (3, 4)}')[:-1])
        self.assertEqual([join(part) for part in parts], ['a=0', 'a<len([1,2])', '{f"x":(3,4)}'])

    def testScanner(self):
        """Each token is the longest match, whichever characters are next to it."""
        for line, expected in [
            ('t-$10',         ['t', '-', '0x10']),
            ('-$10',          ['-', '0x10']),
            ('2*%11',         ['2', '*', '0b11']),
            ('$20/$10',       ['0x20', '/', '0x10']),
            ('~$10',          ['~', '0x10']),
            ('2**$4',         ['2', '**', '0x4']),
            ('16//$4',        ['16', '//', '0x4']),
            ('7%$10',         ['7', '%', '0x10']),
            ('%101%2',        ['0b101', '%', '2']),
            ('a<<2',          ['a', '<<', '2']),
            ('a<=2',          ['a', '<=', '2']),
            ('a==-1',         ['a', '==', '-', '1']),
            ('a!=b',          ['a', '!=', 'b']),
            ('x=.5',          ['x', '=', '.', '5']),
            ('a<.5',          ['a', '<', '.', '5']),
            ('1.5',           ['1.5']),
            ('1e3',           ['1e3']),
            ('1.5e-3',        ['1.5e-3']),
            ('1e-_x',         ['1e', '-', '_x']),
            ('a-1',           ['a', '-', '1']),
            ('.byte 1 ; c',   ['.', 'byte', '1']),
            ('; c',           []),             # a line with only a comment
            ('.byte %10, 0b10', ['.', 'byte', '0b10', ',', '0b10']),
            ('.byte $10, 0x10', ['.', 'byte', '0x10', ',', '0x10']),
            ('.byte 10',      ['.', 'byte', '10']),
            ('l:nop',         ['l', ':', 'nop']),
            ('"a;b" ; c',     ['f"a;b"']),
            ('"a\\"b"',       ['f"a\\"b"']),
            ("'a;b'",         ["'a;b'"]),
            ('r"a"',          ['r"a"']),
            ('f"a"',          ['f"a"']),
            ('x = "abc',      ['x = "abc']),   # no closing quote: one token, reported as invalid syntax
            ("x = 'abc",      ["x = 'abc"]),
        ]:
            with self.subTest(line=line):
                self.assertEqual([t.string for t in translateLocalLabels(tokenize(line))[:-1] if t.string != '\n'], expected)

    def testLocalLabelNames(self):
        """A local label is named global_local, after the last global label. Before any global label, or in all capitals, it isn't changed."""
        for source, expected in [
            ('a: nop\n_b: bne _b',  ['a', ':', 'nop', 'a_b', ':', 'bne', 'a_b']),
            ('a:\nc:\n_b: nop',     ['a', ':', 'c', ':', 'c_b', ':', 'nop']),
            ('_b: nop',             ['_b', ':', 'nop']),
            ('g: nop\n_B: bne _B',  ['g', ':', 'nop', '_B', ':', 'bne', '_B']),
        ]:
            with self.subTest(source=source):
                self.assertEqual([t.string for t in translateLocalLabels(tokenize(source))[:-1] if t.string != '\n'], expected)

    def testPythonBlock(self):
        """A .python block becomes one .python line with the code as a string, keeping the line count."""
        strings = [t.string for t in tokenize('nop\n.python\n    def f(x):\n        return x; # a;b\n.end\nrts')]
        self.assertEqual(strings[:5], ['nop', '\n', '.', 'python', repr('def f(x):\n    return x; # a;b')])
        self.assertEqual(strings[5:], ['\n'] * 4 + ['rts', '\n'])

    def testTokenizeMissingFile(self):
        """A missing file raises FileNotFoundError, for the caller to handle."""
        self.assertRaises(FileNotFoundError, tokenizeFile, os.path.join(os.path.dirname(__file__), 'missing.asm'))

    def testSplitByNewline(self):
        """The tokens of each line, without the newlines. An empty line has no tokens."""
        tokens = [Token('a'), Token('\n'), Token('b'), Token('c'), Token('\n'), Token('\n'), Token('d')]
        lines = [[token.string for token in lineTokens] for lineTokens in splitByNewline(tokens)]
        self.assertEqual(lines, [['a'], ['b', 'c'], [], ['d']])


if __name__ == '__main__':
    unittest.main()
