#! /usr/bin/env python3
"""Tests of the assembler."""

import contextlib
import io
import os
import struct
import tempfile
import unittest

from .. import directives
from ..context import Context
from ..assemble import assembleFile, MAX_PASSES, TARGETS


class TestAssemble(unittest.TestCase):
    """Tests of assembling source files: messages, files, and the .prg output."""

    def _assemble(self, source: str):
        """Assemble source, and return (anyErrors, printed output and messages)."""
        with tempfile.TemporaryDirectory() as directory:
            filename = os.path.join(directory, 'test.asm')
            with open(filename, 'w') as f:
                f.write(source)
            with contextlib.redirect_stdout(io.StringIO()) as output:
                context = assembleFile(filename)
        messages = ''.join(f'{message}\n' for message in context.printed + context.warnings + context.errors)
        return len(context.errors) > 0, output.getvalue() + messages

    def testDuplicateLabel(self):
        """A label can only be defined once."""
        anyErrors, output = self._assemble('a: nop\n'
                                           'a: nop\n')
        self.assertTrue(anyErrors)
        self.assertIn('test.asm:2: error: Label was already defined: "a"', output)

    def testConstants(self):
        """Only all upper case symbols are constants, including the built-in ones."""
        anyErrors, output = self._assemble('myValue = 1\n'
                                           'myValue = 2\n'
                                           'MyValue = 1\n' # capitals and lower case: a variable
                                           'MyValue = 2\n')
        self.assertFalse(anyErrors, output)

        # built-in constants, from the imports folder
        anyErrors, output = self._assemble('STACK_ADDRESS = $100\n')
        self.assertFalse(anyErrors, output)
        anyErrors, output = self._assemble('STACK_ADDRESS = 1\n')
        self.assertIn('test.asm:1: error: Constant "STACK_ADDRESS" cannot be changed from 256 to 1', output)

    def testSymbolTypes(self):
        """A symbol keeps its type, e.g. an int can't become a str."""
        anyErrors, output = self._assemble('x = 1\n'
                                           'x = 2\n'
                                           'name = "a"\n'
                                           'name = "b"\n'
                                           'f = lambda v: v\n'
                                           'f = lambda v: v + 1\n')
        self.assertFalse(anyErrors, output)

        for source, message in [
            ('x = 1\n'
             'x = "a"\n',  'test.asm:2: error: Symbol "x" cannot change type from int to str'),
            ('f = lambda v: v\n'
             'f = 1\n',    'test.asm:2: error: Symbol "f" cannot change type from function to int'),
            ('x = "a"\n'
             'x: nop\n',   'test.asm:2: error: Symbol "x" cannot change type from str to int'),
            ('x = zp(1)\n'
             'x = "a"\n',  'test.asm:2: error: Symbol "x" cannot change type from int to str'),
            # the math module is protected
            ('pi = 3\n',   'test.asm:1: error: Symbol "pi" cannot change type from float to int'),
            ('e: nop\n',   'test.asm:1: error: Symbol "e" cannot change type from float to int'),
            ('sin: nop\n', 'test.asm:1: error: Symbol "sin" cannot change type from builtin_function_or_method to int'),
        ]:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertIn(message, output)

    def testByteWordNotInt(self):
        """A .byte or .word value that isn't an int is one error, such as a string or a function."""
        for source, value in [
            ('.byte "B"',                    "'B'"),
            ('.word "B"',                    "'B'"),
            ('.bytefill 1, lambda x: "B"',   "'B'"),
            ('.wordfill 1, lambda x: "B"',   "'B'"),
            ('.byte print',                  '<built-in function print>'),
            ('.word print',                  '<built-in function print>'),
            ('.bytefill 1, lambda x: print', '<built-in function print>'),
            ('.wordfill 1, lambda x: print', '<built-in function print>'),
        ]:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(f'{source}\n')
                self.assertEqual(len(output.splitlines()), 1)
                self.assertIn(f'test.asm:1: error: Expected an int value instead of: "{value}"', output)

    def testFillFunctionError(self):
        """Each value the fill function fails for is an error, with the index."""
        for source, expected in [
            ('.wordfill 4, lambda x: [5, 6][x]\n', ['test.asm:1: error: List index out of range, at index 2',
                                                   'test.asm:1: error: List index out of range, at index 3']),
            ('.bytefill 2, lambda x: {0: 1}[x]\n', ['test.asm:1: error: KeyError: 1, at index 1']),     # the type, as the text is only the key
            ('.python\n'
             'def check(x):\n'
             '    assert x < 2\n'
             '    return x\n'
             '.end\n'
             '.bytefill 4, check\n',               ['test.asm:6: error: AssertionError, at index 2',   # the type, as there is no text
                                                   'test.asm:6: error: AssertionError, at index 3']),
        ]:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertEqual([line[line.index('test.asm'):] for line in output.splitlines()], expected) # without the folder

    def testFillErrorSize(self):
        """A fill keeps its size when values fail, as they are zero, so the addresses after it stay the same."""
        for source, size in [
            ('.bytefill 4, lambda x: nothing\n'
             '.print _ - $1000\n', '4'), # fails for every value
            ('.bytefill 4, lambda x: [1][x]\n'
             '.print _ - $1000\n', '4'), # fails from the second value
            ('.wordfill 3, lambda x: 70000\n'
             '.print _ - $1000\n', '6'), # values out of range
        ]:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertTrue(anyErrors)
                self.assertIn(size, output.splitlines())

    def testFillWarning(self):
        """Each fill value that is a truncated float is a warning."""
        anyErrors, output = self._assemble('.bytefill 4, lambda x: x / 2\n')
        self.assertEqual([line[line.index('test.asm'):] for line in output.splitlines()],
                         ['test.asm:1: warning: Truncating float value: 0.5',
                          'test.asm:1: warning: Truncating float value: 1.5'])

    def testForLoopLimit(self):
        """A .for loop over an endless iterable is an error, not a hang."""
        from unittest import mock
        with mock.patch.object(directives, 'MAX_ITERATIONS', 100): # the real limit takes seconds
            anyErrors, output = self._assemble('.for a in iter(int, 1)\n' # int() is never 1, so it never ends
                                               '.end\n')
        self.assertIn('test.asm:2: error: For loop did not end after 100 iterations', output)

    def testFilePaths(self):
        """.binary and @importMusic read files relative to the folder of the main source file, not the current folder."""
        with tempfile.TemporaryDirectory() as directory:
            # a PSID header: version 2, data at $7c, load and init at $2000, play at $2003, and one song
            sid = struct.pack('>4sHHHHHHHL32s32s32sHBBBB', b'PSID', 2, 0x7c, 0x2000, 0x2000, 0x2003, 1, 1, 0, b'', b'', b'', 0, 0, 0, 0, 0)
            for name, data in [('paths.bin', b'\x01\x02'), ('paths.sid', sid + b'\x60')]:
                with open(os.path.join(directory, name), 'wb') as f:
                    f.write(data)
            asmFile = os.path.join(directory, 'paths.asm')
            with open(asmFile, 'w') as f:
                f.write('.binary "paths.bin"\n'
                        '.org M_LOAD\n'
                        '@importMusic("paths.sid", "M")\n')
            context = assembleFile(asmFile, target='c64')
            self.assertEqual(context.errors, [])
            self.assertEqual((context.memory[0x1000], context.memory[0x1001], context.memory[0x2000]), (0x01, 0x02, 0x60))

    def testBinaryOffsetLength(self):
        """.binary stores the whole file, or from an offset, or from an offset with a length, also as keyword
        arguments."""
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, 'data.bin'), 'wb') as f:
                f.write(bytes([1, 2, 3, 4, 5]))
            asmFile = os.path.join(directory, 'data.asm')
            for source, expected in [('.binary "data.bin"\n',                     [1, 2, 3, 4, 5]),
                                     ('.binary "data.bin", 2\n',                  [3, 4, 5]),
                                     ('.binary "data.bin", 1, 2\n',               [2, 3]),
                                     ('.binary "data.bin", length=2\n',           [1, 2]),
                                     ('.binary "data.bin", offset=1, length=2\n', [2, 3]),
                                     ('.binary filename="data.bin", length=1\n',  [1]),    # the names in the README
                                     ('options = {"offset": 3}\n'
                                      '.binary "data.bin", **options\n',          [4, 5])]:
                with self.subTest(source=source):
                    with open(asmFile, 'w') as f:
                        f.write(source)
                    context = assembleFile(asmFile)
                    self.assertEqual(context.errors, [])
                    self.assertEqual(list(context.memory.values()), expected)

    def _assertMessages(self, cases: list):
        """Assemble each source, and check the output has its message, at the line that causes it."""
        for source, message in cases:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertIn(message, output)

    def testMemoryMessages(self):
        """Storing outside memory, or over bytes already stored."""
        self._assertMessages([
            ('.org $1000\n'
             '.byte 1\n'
             '.org $1000\n'
             '.byte 2\n',    'test.asm:4: warning: $1000 is overwritten ($01 to $02)'),
            ('.org $ffff\n'
             '.byte 1, 2\n', 'test.asm:2: error: Destination memory address out of range: $10000'),
        ])

    def testCPUMessages(self):
        """.cpu needs a cpu, and each pass starts with the 6502 again."""
        self._assertMessages([
            ('.cpu 7\n',         'test.asm:1: error: Invalid directive: .cpu 7'),
            ('.cpu "65C02"\n',   'test.asm:1: error: Invalid directive: .cpu f"65C02"'),                          # a string, not a cpu
            ('stz $10\n'
             '.cpu CPU_65C02\n', 'test.asm:1: error: Not an instruction of the 6502: "stz", see .cpu and --cpu'), # not from the last pass
            ('.cpu CPU_65C02\n'
             'lax $10\n',        'test.asm:2: error: Not an instruction of the 65C02: "lax", see .cpu and --cpu'),
            ('wai\n',            'test.asm:1: error: Not an instruction of the 6502: "wai", see .cpu and --cpu'),
            ('CPU_6502 = 1\n',   'test.asm:1: error: Constant "CPU_6502" cannot be changed from CPU(\'6502\') to 1'),
        ])

    def testValueMessages(self):
        """Directive and instruction values that are unknown or not allowed."""
        self._assertMessages([
            ('.text "a"\n',                        'test.asm:1: error: Unknown character "a" in text "a"'),
            ('.text 65\n',                         'test.asm:1: error: Invalid directive: .text 65'),
            ('.string "A", 65\n',                  'test.asm:1: error: Invalid directive: .string f"A",65'),
            ('.text ["A"]\n',                      'test.asm:1: error: Invalid directive: .text [f"A"]'),
            ('.align 0\n',                         'test.asm:1: error: Alignment must be positive: 0'),
            ('.bytefill -2\n',                     'test.asm:1: error: Count must not be negative: -2'),
            ('.wordfill -1, lambda x: x\n',        'test.asm:1: error: Count must not be negative: -1'),
            ('.org undefinedSymbol\n',             'test.asm:1: error: Name \'undefinedSymbol\' is not defined: "undefinedSymbol"'),
            ('hello world\n',                      'test.asm:1: error: Invalid syntax'),
            ('lda #MAX_Speed\n',                   'test.asm:1: error: Name \'MAX_Speed\' is not defined: "MAX_Speed"'), # only the first letter capitalized
            ('.bytefill 1, lambda x: MAX_Speed\n', 'test.asm:1: error: Name \'MAX_Speed\' is not defined, at index 0\n'),
            ('.byte {0: 1}[1]\n',                  'test.asm:1: error: KeyError: 1: "{0:1}[1]"'),
            ('point = (24, 50)\n'
             '.byte point\n',                       'test.asm:2: error: Expected an int value instead of: "(24, 50)"'), # one argument, as in Python
            ('.binary "data.bin", size=2\n',       'test.asm:1: error: Invalid directive: .binary f"data.bin",size=2'), # no such parameter
            ('.byte 1), (2), (3\n',                'test.asm:1: error: Invalid directive: .byte 1),(2),(3'),             # brackets that end the call early
            ('.byte 1) and (2\n',                  'test.asm:1: error: Invalid directive: .byte 1)and(2'),
        ])

    def testReportMessages(self):
        """.print, .warning and .error report their text."""
        self._assertMessages([
            ('.print 1 + 1\n',       '2\n'),
            ('.warning "careful"\n', 'test.asm:1: warning: careful'),
            ('.error "stop"\n',      'test.asm:1: error: stop'),
        ])

    def testOneErrorPerFailure(self):
        """An expression that fails is one error, and nothing is assembled from it, e.g. no .repeat block."""
        for source in ['lda nothing\n',
                       'jsr nothing\n',
                       'nothing = nothing\n',
                       '.repeat nothing\n'
                       '.byte 1\n'
                       '.end\n',
                       '@nothing()\n']:
            with self.subTest(source=source):
                context = self._assembleForTarget(source)
                self.assertEqual(len(context.errors), 1, context.errors)
                self.assertIn('test.asm:1: error: Name \'nothing\' is not defined', context.errors[0])
                self.assertNotIn(1, context.memory.values()) # the .repeat block is skipped

    def testUnderscoreAttributes(self):
        """An attribute starting with _ after a dot is Python's, also after a global label, e.g. t._x and f.__name__."""
        anyErrors, output = self._assemble('.python\n'
                                           'class T:\n'
                                           '    _x = 5\n'
                                           't = T()\n'
                                           '.end\n'
                                           'start:     .byte t._x\n'
                                           '           .print start.__class__.__name__\n'
                                           '_loop:     bne _loop\n') # still a local label
        self.assertFalse(anyErrors, output)
        self.assertEqual(output, 'int\n')

    def testAssignNone(self):
        """None is a value like any other, so it can be assigned."""
        anyErrors, output = self._assemble('flag = None\n'
                                           '.print flag\n'
                                           '.print flag is None\n')
        self.assertFalse(anyErrors, output)
        self.assertEqual(output, 'None\nTrue\n')

    def testPrintNone(self):
        """.print None prints None, as a value like any other."""
        anyErrors, output = self._assemble('.print None\n')
        self.assertFalse(anyErrors)
        self.assertEqual(output, 'None\n')

    def testAssertMessages(self):
        """A failed .assert, and an .assert with the wrong arguments."""
        self._assertMessages([
            ('.assert 2 > 3\n',     'test.asm:1: error: Assertion failed'),
            ('.assert 2 > 3, "Something is wrong"\n', 'test.asm:1: error: Something is wrong'),
            ('.assert\n',           'test.asm:1: error: Invalid directive: .assert'),
            ('.assert 2 > 3, 42\n', 'test.asm:1: error: Invalid directive: .assert'), # the message must be a string
        ])

    def testBlockMessages(self):
        """Blocks that are not opened or closed correctly."""
        self._assertMessages([
            ('.end\n',                 'test.asm:1: error: End without matching repeat, for or if'),
            ('.else\n',                'test.asm:1: error: Else without matching if'),
            ('.if 1\n'
             '.else\n',                'test.asm:2: error: Else without matching end'),
            ('.elif 1\n',              'test.asm:1: error: Elif without matching if'),
            ('.if 0\n'
             '.else\n'
             '.elif 1\n'
             '.end\n',                 'test.asm:3: error: Elif after else'),
            ('.if 0\n'
             '.elif nothing\n'
             '.end\n',                 'test.asm:2: error: Name \'nothing\' is not defined: "nothing"'),            # at the .elif
            ('.repeat "i", 2\n'
             '.end\n',                 'test.asm:1: error: Expected .repeat count'),                                 # the count must be a number
            ('.for a\n',               'test.asm:1: error: Expected .for target in iterable: .for a'),
            ('.for a=0, a<4, a+=1\n',  'test.asm:1: error: Expected .for target in iterable: .for a=0,a<4,a+=1'),    # not C-style
            ('.for a+1 in range(2)\n', 'test.asm:1: error: Expected .for target in iterable: .for a+1 in range(2)'), # not a name
            ('.python\n'
             'x = 1\n',                'test.asm:1: error: Invalid directive: .python'),                             # no .end
        ])

    def testElseUsedTwice(self):
        """A second .else is one error, and its .if is still open, so the .end matches it."""
        errors = self._assembleForTarget('.if 0\n'
                                         '.else\n'
                                         '.else\n'
                                         '.end\n'
                                         '.byte 1\n').errors
        self.assertEqual(len(errors), 1, errors)
        self.assertIn('test.asm:3: error: Else after else', errors[0])

    def testPythonMessages(self):
        """Python code that fails, in .python and .import."""
        self._assertMessages([
            ('.python\n'
             '1/0\n'
             '.end\n',                 'test.asm:1: error: Failed to execute python code: "1/0" (ZeroDivisionError: division by zero)'),
            ('.python "1/0"\n',        'test.asm:1: error: Invalid syntax'), # only python blocks
            ('.import "nothere.py"\n', 'test.asm:1: error: Failed to execute python code: "nothere.py" (FileNotFoundError: '),
        ])

    def testForMessages(self):
        """A .for that isn't a for loop, an iterable that fails or isn't iterable, or a value that doesn't unpack into
        the names, is one error, and the lines up to .end are skipped.
        A value after the first is assigned, and reported, at the .end."""
        for source, expected in [
            ('.for a\n'
             '.byte 1\n'
             '.end\n', ['test.asm:1: error: Expected .for target in iterable: .for a']),
            ('.for a=0, a<2, a+=1\n'
             '.byte a\n'
             '.end\n', ['test.asm:1: error: Expected .for target in iterable: .for a=0,a<2,a+=1']),      # C-style
            ('.for a in range(2)\x00\n'
             '.byte a\n'
             '.end\n', ['test.asm:1: error: Expected .for target in iterable: .for a in range(2)\x00']), # Python 3.11 raises ValueError
            ('.for a in nothing\n'
             '.byte a\n'
             '.end\n', ['test.asm:1: error: Name \'nothing\' is not defined: "nothing"']),
            ('.for a in 5\n'
             '.byte a\n'
             '.end\n', ['test.asm:1: error: \'int\' object is not iterable: "5"']),
            ('.for a, b in [1]\n'
             '.byte a\n'
             '.end\n', ['test.asm:1: error: Cannot unpack non-iterable int object: "a,b"']),
            ('.for a, b in [(1,)]\n'
             '.byte a\n'
             '.end\n', ['test.asm:1: error: Not enough values to unpack (expected 2, got 1): "a,b"']),
            ('.for a, b in [(1, 2), 3]\n'
             '.byte a\n'
             '.end\n', ['test.asm:3: error: Cannot unpack non-iterable int object: "a,b"']),             # the second value
            ('.for a in ({0: 1}[x] for x in [0, 1])\n'
             '.byte a\n'
             '.end\n', ['test.asm:3: error: KeyError: 1: "a"']),                                        # in the iterable
        ]:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertEqual([line[line.index('test.asm'):] for line in output.splitlines()], expected)

    def testFileMessages(self):
        """Files that are not found."""
        self._assertMessages([
            ('.import "nothere.asm"\n', 'test.asm:1: error: File not found: "nothere.asm"'),
            ('.binary "nothere.bin"\n', 'test.asm:1: error: File not found: "nothere.bin"'),
        ])

    def testNestingMessages(self):
        """A file that imports itself, or a generator that calls itself, is an error at the first line nested
        too deep, and assembly ends."""
        self._assertMessages([
            ('.import "test.asm"\n', 'test.asm:1: error: Imports and generators nested more than 100 deep'),
            ('.python\n'
             'def again():\n'
             '    return "@again()"\n'
             '.end\n'
             '@again()\n',            ' @again():1: error: Imports and generators nested more than 100 deep'),
        ])

    def testUnclosedBlockMessages(self):
        """A block without .end gives an error at the line that started it."""
        self._assertMessages([
            ('.repeat 2\n'
             'nop\n',  'test.asm:1: error: Repeat without matching end'),
            ('.for a in range(2)\n'
             'nop\n',  'test.asm:1: error: For without matching end'),
            ('.if 1\n'
             'nop\n',  'test.asm:1: error: If without matching end'),
            ('.if 0\n'
             '.else\n'
             'nop\n',  'test.asm:2: error: If without matching end'),     # at the .else
            ('nop\n'
             '.repeat 2\n'
             '.if 1\n'
             '.end\n', 'test.asm:2: error: Repeat without matching end'), # the outer block
        ])

    def _memory(self, source: str, target: str | None = None) -> list:
        """Assemble source for the target without errors, and return the bytes in memory, by address."""
        with tempfile.TemporaryDirectory() as directory:
            filename = os.path.join(directory, 'test.asm')
            with open(filename, 'w') as f:
                f.write(source)
            context = assembleFile(filename, target=target)
        self.assertEqual(context.errors, [])
        return [context.memory[address] for address in sorted(context.memory)]

    def testEncoding(self):
        """.encoding chooses the text encoding, for .text, ord() and chr()."""
        self.assertEqual(self._memory('.encoding ENCODING_SCREEN_UPPER\n'
                                      '.text "A"\n'
                                      '.encoding ENCODING_SCREEN_MIXED\n'
                                      '.text "A"\n'
                                      '.encoding ENCODING_PETSCII_UPPER\n'
                                      '.text "A"\n'
                                      '.encoding ENCODING_PETSCII_MIXED\n'
                                      '.text "A"\n'), [0x01, 0x41, 0x41, 0x61]) # A in each encoding

    def testMaxPasses(self):
        """A source with an error that doesn't go away is assembled MAX_PASSES times, the most passes."""
        anyErrors, output = self._assemble('.python\n'
                                           'passes = globals().get("passes", 0) + 1\n' # the symbols are kept between passes
                                           '.end\n'
                                           '.print passes\n'
                                           '.byte nothing\n')
        self.assertTrue(anyErrors)
        self.assertTrue(output.startswith(f'{MAX_PASSES}\n'), output)

    def testUnresolved(self):
        """A source whose output still changes in the last pass is an error, and nothing else is."""
        links = MAX_PASSES - 4 # one block more than the longest chain in testRef
        source = '.word f0\n' + ''.join(f'.if ref("f{i}")\n'
                                         f'f{i}: .word f{i + 1}\n'
                                         '.end\n' for i in range(links)) + (f'.if ref("f{links}")\n'
                                                                             f'f{links}: .byte 9\n'
                                                                             '.end\n')
        anyErrors, output = self._assemble(source)
        self.assertTrue(anyErrors)
        self.assertRegex(output, r'^error: Failed to assemble: ".*test\.asm"\n$') # the source file, in the folder of the test

    def testEncodingEachPass(self):
        """Every pass starts with the default encoding, whichever encoding the previous pass ended with."""
        self.assertEqual(self._memory("""
            .text "A"                           ; default encoding, screen code upper
            .byte ord("A")
            .byte int(chr(1) == "A")

            .encoding ENCODING_PETSCII_UPPER
            .text "A"
            .byte ord("A")
            .byte int(chr(65) == "A")

            .encoding ENCODING_SCREEN_UPPER     ; switching back to screen code
            .text "A"

            .encoding ENCODING_PETSCII_MIXED    ; would leak into the next pass
            .text "A"
            """), [0x01, 0x01, 0x01, 0x41, 0x41, 0x01, 0x01, 0x61])

    def testCustomEncoding(self):
        """An encoding is a table of characters and values, so .encoding also takes your own, for .text, ord() and chr()."""
        self.assertEqual(self._memory('MY_FONT = {"A": 0, "B": 1}\n'
                                      '.encoding MY_FONT\n'
                                      '.text "BA"\n'
                                      '.byte ord("B")\n'
                                      '.byte int(chr(0) == "A")\n'), [1, 0, 1, 1])
        self.assertEqual(self._memory('.encoding {"A": -1}\n'
                                      '.string "A"\n'), [0xff, 0]) # -1 in two's complement

    def testEncodingMessages(self):
        """.encoding needs an encoding, and its values must fit in a byte."""
        self._assertMessages([
            ('.encoding 7\n',   'test.asm:1: error: Invalid directive: .encoding 7'),
            ('.encoding "A"\n', 'test.asm:1: error: Invalid directive: .encoding f"A"'),
            ('.encoding {"A": 1}\n'
             '.text "B"\n',     'test.asm:2: error: Unknown character "B" in text "B"'),
            ('.encoding {"A": 300}\n'
             '.text "A"\n',     'test.asm:2: error: Byte value out of range: 300'),
            ('.encoding {"A": "x"}\n'
             '.text "A"\n',     'test.asm:2: error: Expected an int value instead of: "\'x\'"'),
        ])

    def testLocalLabels(self):
        """A local label belongs to the global label before it, so a name can be used again after the next one."""
        self.assertEqual(self._memory('aa: nop\n'
                                      '_0: jmp _1\n'
                                      'nop\n'
                                      '_1: jmp _0\n'
                                      'bb: nop\n'
                                      '_0: jmp _0\n'),
                         [0xea, 0x4c, 0x05, 0x10, 0xea, 0x4c, 0x01, 0x10, 0xea, 0x4c, 0x09, 0x10]) # aa_0 jumps to aa_1, aa_1 to aa_0, and bb_0 to itself

    def testLocalLabelFromOutside(self):
        """A local label can be used by its full name, global_local, from anywhere."""
        self.assertEqual(self._memory('aa: nop\n'
                                      '_x: nop\n'
                                      'bb: jmp aa_x\n'), [0xea, 0xea, 0x4c, 0x01, 0x10])

    def testLocalLabelWithoutGlobal(self):
        """A local label needs a global label before it."""
        self._assertMessages([
            ('_x: nop\n', 'test.asm:1: error: Local label without a global label before it: "_x"'),
            ('nop\n'
             '_x: nop\n'
             'g: nop\n',  'test.asm:2: error: Local label without a global label before it: "_x"'),
        ])

    def testLabelInCapitals(self):
        """Capitals are for constants, so a label, global or local, can't be all capitals."""
        self._assertMessages([
            ('VIC: nop\n',              'test.asm:1: error: Capitals are for constants, not labels: "VIC"'),
            ('VIC_BORDER_COLOR: nop\n', 'test.asm:1: error: Capitals are for constants, not labels: "VIC_BORDER_COLOR"'),
            ('A: nop\n',                'test.asm:1: error: Capitals are for constants, not labels: "A"'),
            ('TABLE2: nop\n',           'test.asm:1: error: Capitals are for constants, not labels: "TABLE2"'),
            ('g:\n'
             '_LOOP: nop\n',            'test.asm:2: error: Capitals are for constants, not labels: "_LOOP"'),
            ('.python\n'
             'def f():\n'
             '    return "_X: nop\\n"\n'
             '.end\n'
             '@f()\n',                  'test.asm:5 @f():1: error: Capitals are for constants, not labels: "_X"'),
            ('_X: nop\n',               'test.asm:1: error: Capitals are for constants, not labels: "_X"'),
        ])
        for source in [
            'Level: nop\n',
            'level2: nop\n',
            'playerX: nop\n',
            'g:\n'
            '_Loop: nop\n',
            'g:\n'
            '_0: nop\n', # digits only
            'VICe:\n' # mixed case
            '_BORDER2x: nop\n',
            '.python\n'
            '_MAX = 5\n'
            '.end\n'
            'g: lda #_MAX\n', # a Python name, not a label
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._assembleForTarget(source).errors, [])

    def testPythonKeywords(self):
        """Python keywords work in directives, instructions, assignments and generators."""
        for source, expected in [
            ('.byte 1 if flag else 2\n',                 [1]),
            ('.byte 3 if not flag else 4\n',             [4]),
            ('.byte flag and 5, flag or 6\n',            [5, 1]),   # and gives 5, or gives flag
            ('.byte 7 if 3 in [1, 2, 3] else 8\n',       [7]),
            ('.word $1234 if flag is not None else 0\n', [0x34, 0x12]),
            ('lda #9 if flag else 10\n',                 [0xa9, 9]),
            ('squares = [x * x for x in range(4)]\n'
             '.byte squares[3]\n',                       [9]),
            ('.python\n'
             '    def fill(x, n):\n'
             '        return f".byte {x}\\n" * n\n'
             '.end\n'
             '@fill(11, 2) if flag else ""\n',           [11, 11]), # a generator call in an expression
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._memory(f'flag = 1\n{source}'), expected)

    def testFormattedStrings(self):
        """A double-quoted string can use symbols, as in a Python f-string."""
        self.assertEqual(self._memory('a = "ABC"\n'
                                      '\tb = 123\n' # an assignment can be indented, also with a tab
                                      '.text "{a} {b}"\n'), [1, 2, 3, 0x20, 0x31, 0x32, 0x33]) # ABC, a space and 123, in screen codes

    def testLoHi(self):
        """lo() and hi() are the low and the high byte of a value."""
        self.assertEqual(self._memory('.byte lo($1234)\n'
                                      '.byte hi($1234)\n'), [0x34, 0x12])

    def testModulo(self):
        """% is both the binary prefix and the Python modulo operator."""
        for source, expected in [
            ('.byte 7 % 4\n',      [3]),          # spaces on both sides
            ('.byte 7%4\n',        [3]),          # no spaces
            ('.byte 10 %4\n',      [2]),          # %4 is not binary
            ('.byte 6 % %11\n',    [0]),          # 6 % 3
            ('.byte %101 % 3\n',   [2]),          # 5 % 3
            ('.byte (%101) % 3\n', [2]),          # 5 % 3, binary inside parentheses
            ('.byte 7 %11\n',      [7]),          # 7 % 11, after a number
            ('.byte x %10\n',      [7]),          # 7 % 10, after a name
            ('.byte (5) %10\n',    [5]),          # 5 % 10, after a parenthesis
            ('.byte %11\n',        [3]),          # a binary prefix right after a directive
            ('lda %11\n',          [0xa5, 0x03]), # and after a mnemonic
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._memory(f'x = 7\n{source}'), expected)

    def testRef(self):
        """ref(label) is true if the label was referenced in the last pass, wherever and however."""
        block = ('.if ref("t")\n'
                 't: .byte 8\n'
                 '.end\n')
        # each block assembled only when the one before it is, a pass later: the longest chain, which settles in MAX_PASSES
        links = MAX_PASSES - 5
        chain = ''.join(f'.if ref("f{i}")\n'
                        f'f{i}: .word f{i + 1}\n'
                        '.end\n' for i in range(links)) + (f'.if ref("f{links}")\n'
                                                            f'f{links}: .byte 9\n'
                                                            '.end\n')
        for source, expected in [
            ('.byte 0\n' + block,      [0]),                         # not referenced
            ('.word t\n' + block,      [0x02, 0x10, 8]),
            (block + '.word t\n',      [8, 0x00, 0x10]),             # referenced after the block
            ('.word a\n'
             '.if ref("a")\n'
             'a: .word b\n'
             '.end\n'
             '.if ref("b")\n'
             'b: .byte 9\n'
             '.end\n',                 [0x02, 0x10, 0x04, 0x10, 9]), # by a block
            ('.word f0\n' + chain,     [0x02, 0x10] + [x for i in range(links) for x in (0x04 + 2 * i, 0x10)] + [9]), # the whole chain
            ('.byte 0\n' + chain,      [0]),                         # nothing to start the chain
            ('.byte 0\n'
             '.if ref("s")\n'
             's: .word s\n'
             '.end\n',                 [0]),                         # only by itself
            ('.byte 0\n'
             '.if ref("x")\n'
             'x: .word y\n'
             '.end\n'
             '.if ref("y")\n'
             'y: .word x\n'
             '.end\n',                 [0]),                         # only by each other
            ('.if 0\n'
             '.word t\n'
             '.end\n'
             '.byte 0\n' + block,      [0]),                         # not referenced if skipped
            ('.print "t"\n'
             '.byte 0\n' + block,      [0]),                         # text in a string
            ('.print \'t\'\n'
             '.byte 0\n' + block,      [0]),
            (".if ref('t')\n"
             "t: .byte 8\n"
             ".end\n"
             ".byte 0\n",              [0]),                         # single quotes
            ('.print "{t}"\n' + block, [8]),                         # an expression in a string
            ('lda #lo(t)\n' + block,   [0xa9, 0x02, 8]),             # in an expression
            ('.bytefill 1, lambda x: lo(t)\n' + block, [0x01, 8]),   # in a lambda
            ('@"jmp t"\n' + block,     [0x4c, 0x03, 0x10, 8]),       # by generated code
            ('.python\n'
             'def f():\n'
             '    return t\n'
             '.end\n'
             '.word f()\n' + block,    [0x02, 0x10, 8]),             # by Python code
            ('.if ref("t")\n'
             't: .byte 8\n'
             '.else\n'
             '.byte 7\n'
             '.end\n',                 [7]),                         # with .else
            ('.if ref("nothing")\n'
             '.byte 1\n'
             '.end\n',                 []),
        ]:
            with self.subTest(source=source[:50]):
                self.assertEqual(self._memory(source), expected)

    def testHas(self):
        """has(instruction) is true if that line would assemble on the current cpu."""
        for cpu, instruction, expected in (
            ('CPU_6502',   'lax $12',       True),
            ('CPU_65C02',  'lax $12',       False), # an illegal instruction: not on the CMOS cpus
            ('CPU_6502',   'lax',           False), # not a line that assembles, without an operand
            ('CPU_6502',   'lax #5',        False), # no such mode, as it is unstable
            ('CPU_6502',   'bit #1',        False), # a mode only some cpus have
            ('CPU_65C02',  'bit #1',        True),
            ('CPU_6502',   'bit $12',       True),
            ('CPU_6502',   'stz $12',       False),
            ('CPU_65C02',  'stz $12',       True),
            ('CPU_6502',   'inc',           False), # the accumulator
            ('CPU_65C02',  'inc',           True),
            ('CPU_6502',   'asl',           True),
            ('CPU_65C02',  'rmb1 $12',      False),
            ('CPU_R65C02', 'rmb1 $12',      True),
            ('CPU_R65C02', 'stp',           False),
            ('CPU_W65C02', 'stp',           True),
            ('CPU_6502',   'stx $1234,y',   False), # only the zero page form
            ('CPU_6502',   'stx $12,y',     True),
            ('CPU_65C02',  'lda ($12)',     True),
            ('CPU_6502',   'jmp ($1234)',   True),
            ('CPU_6502',   'lda ($12),y',   True),
            ('CPU_6502',   'lda ($12,x)',   True),
            ('CPU_6502',   'jmp ($1234,x)', False),
            ('CPU_65C02',  'jmp ($1234,x)', True),
            ('CPU_6502',   'lda #300',      False), # out of range
        ):
            with self.subTest(cpu=cpu, instruction=instruction):
                anyErrors, output = self._assemble(f'.cpu {cpu}\n'
                                                   f'.print has("{instruction}")\n')
                self.assertFalse(anyErrors, output)
                self.assertEqual(output.strip(), str(expected))

    def testHasFollowsCpu(self):
        """has() answers for the cpu at that line, and chooses a code path."""
        path = ('.if has("lax $12")\n'
                'lax $12\n'
                '.else\n'
                'lda $12\n'
                'tax\n'
                '.end\n')
        self.assertEqual(self._memory(path + '.cpu CPU_65C02\n' + path), [0xa7, 0x12, 0xa5, 0x12, 0xaa]) # lax on the 6502, lda and tax on the 65C02

    def testHasInGenerator(self):
        """A generator can use has() to choose the code."""
        anyErrors, output = self._assemble("@'lax $12' if has('lax $12') else 'nop'\n"
                                           ".print _\n")
        self.assertFalse(anyErrors, output)
        self.assertEqual(output.strip(), str(0x1002)) # lax $12 was assembled, 2 bytes

    def testHasLeavesNoTrace(self):
        """Trying an instruction stores nothing, reports nothing, and is no reference for ref()."""
        for source, expected in (
            ('.print has("nop")\n'
             '.print _\n',                  f'True\n{0x1000}'), # no address change
            ('.print has("sta nothing")\n', 'False'),           # no error
            ('.print has("jmp ($12ff)")\n', 'True'),            # no warning
            ('.print has("sta t")\n'
             '.print ref("t")\n',           'False\nFalse'),    # no reference
        ):
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertFalse(anyErrors, output)
                self.assertEqual(output.strip(), expected)

    def testHasStoresNothing(self):
        """Trying an instruction at an address in use leaves its byte alone."""
        self.assertEqual(self._memory('nop\n'
                                      '.org $1000\n'
                                      '.if has("rts")\n'
                                      '.end\n'), [0xea])

    def testHasTypo(self):
        """A word that is an instruction of no cpu is an error, not a different code path."""
        anyErrors, output = self._assemble('.if has("lxa $12")\n'
                                           'nop\n'
                                           '.end\n')
        self.assertTrue(anyErrors)
        self.assertIn('test.asm:1: error: Not an instruction: "lxa"', output)

    def testPushPullRegisters(self):
        """pushRegisters and pullRegisters use phx, phy, plx and ply on the cpus that have them."""
        for cpu, expected in (
            ('CPU_6502',   [0x48, 0x8a, 0x48, 0x98, 0x48, 0x68, 0xa8, 0x68, 0xaa, 0x68]), # pha, txa, pha, tya, pha, and pla, tay, pla, tax, pla
            ('CPU_65C02',  [0x48, 0xda, 0x5a, 0x7a, 0xfa, 0x68]),                         # pha, phx, phy, and ply, plx, pla
            ('CPU_R65C02', [0x48, 0xda, 0x5a, 0x7a, 0xfa, 0x68]),
            ('CPU_W65C02', [0x48, 0xda, 0x5a, 0x7a, 0xfa, 0x68]),
        ):
            with self.subTest(cpu=cpu):
                self.assertEqual(self._memory(f'.cpu {cpu}\n'
                                              '@pushRegisters()\n'
                                              '@pullRegisters()\n'), expected)

    def testAssignment(self):
        """The value of a Python expression is assigned to the symbol."""
        self.assertEqual(self._memory('x = 1 + 2\n'
                                      '.byte x\n'), [3])

    def testFailedAssignment(self):
        """A symbol is not assigned, if the expression fails."""
        self._assertMessages([
            ('x = undefined\n', "test.asm:1: error: Name 'undefined' is not defined"),
            ('x = undefined\n'
             '.byte x\n',       "test.asm:2: error: Name 'x' is not defined"),
        ])

    def testConstantKeepsValue(self):
        """An upper case symbol can be assigned the same value again, and keeps its value if it can't."""
        self.assertEqual(self._memory('MAX = 1\n'
                                      'MAX = 1\n'
                                      '.byte MAX\n'), [1])
        anyErrors, output = self._assemble('MAX = 1\n'
                                           'MAX = 2\n'
                                           '.print MAX\n')
        self.assertTrue(anyErrors)
        self.assertTrue(output.startswith('1\n'), output)
        self.assertIn('test.asm:2: error: Constant "MAX" cannot be changed from 1 to 2', output)

    def testInvalidAssignmentName(self):
        """Only a Python name can be assigned, so anything else is not an assignment."""
        self._assertMessages([
            ('* = $2000\n', 'test.asm:1: error: Invalid syntax'),
            ('+ = 5\n',     'test.asm:1: error: Invalid syntax'),
            ('- = 1\n',     'test.asm:1: error: Invalid syntax'),
            ('= = 1\n',     'test.asm:1: error: Invalid syntax'),
            ('1 = 2\n',     'test.asm:1: error: Invalid syntax'),
            ('if = 2\n',    'test.asm:1: error: Invalid syntax'),
            ('True = 2\n',  'test.asm:1: error: Invalid syntax'),
        ])

    def testRefOtherSymbols(self):
        """A symbol in a block that is not assembled is not defined."""
        self._assertMessages([
            ('.if ref("t")\n'
             't: nop\n'
             'K = 2\n'
             '.end\n'
             'lda #K\n', "test.asm:5: error: Name 'K' is not defined"),
            ('.if ref("t")\n'
             't: nop\n'
             'v = zp(1)\n'
             '.end\n'
             'lda v\n',  "test.asm:5: error: Name 'v' is not defined"),
        ])

    def testOptional(self):
        """An optional block is only assembled if one of its global labels was referenced in the last pass."""
        table = ('.optional\n'
                 'myTable: .byte 1, 2, 3\n'
                 '.end\n')
        functions = ('.optional\n'
                     'func1: nop\n'
                     'rts\n'
                     'func2: nop\n'
                     'rts\n'
                     '.end\n')
        zeroPage = ('.optional\n'
                    'xyz = zp(1)\n'
                    'func3: lda xyz\n'
                    'rts\n'
                    '.end\n')
        selfUse = ('.optional\n'
                   'func6: dex\n'
                   'bne func6\n'
                   'rts\n'
                   '.end\n')
        for source, expected in [
            ('.byte 0\n' + table,         [0]),                                  # not referenced
            ('.word myTable\n' + table,   [0x02, 0x10, 1, 2, 3]),
            (table + '.word myTable\n',   [1, 2, 3, 0x00, 0x10]),                # referenced after the block
            ('.word func1\n' + functions, [0x02, 0x10, 0xea, 0x60, 0xea, 0x60]), # any of its labels
            ('.word func2\n' + functions, [0x04, 0x10, 0xea, 0x60, 0xea, 0x60]),
            ('.byte 0\n' + zeroPage,      [0]),
            ('.word func3\n' + zeroPage,  [0x02, 0x10, 0xa5, 0x02, 0x60]),
            ('.optional\n'
             '.byte 1, 2, 3\n'
             '.end\n',                    []),                                   # no global labels
            ('.optional\n'
             '_x: .byte 1\n'
             '.end\n',                    []),                                   # only a local label
            ('.byte 0\n' + selfUse,       [0]),                                  # only by itself
            ('jsr func6\n' + selfUse,     [0x20, 0x03, 0x10, 0xca, 0xd0, 0xfd, 0x60]),
            ('.word a\n'
             '.optional\n'
             'a: .word b\n'
             '.end\n'
             '.optional\n'
             'b: .byte 9\n'
             '.end\n',                    [0x02, 0x10, 0x04, 0x10, 9]),          # by a block
            ('.print "myTable"\n'
             '.byte 0\n' + table,         [0]),                                  # text in a string
            ('.word f\n'
             '.optional\n'
             '.if 1\n'
             'f: nop\n'
             '.end\n'
             '.end\n',                    [0x02, 0x10, 0xea]),                   # in an .if in the block
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._memory(source), expected)

    def testOptionalNested(self):
        """A nested block is only assembled if the outer block is, and they each check their own labels."""
        nested = ('.optional\n'
                  'func4: .byte 4\n'
                  '.optional\n'
                  'func5: .byte 5\n'
                  '.end\n'
                  '.end\n')
        self.assertEqual(self._memory('.byte 0\n' + nested), [0])
        self.assertEqual(self._memory('.word func4\n' + nested), [0x02, 0x10, 4])
        self.assertEqual(self._memory('.word func4, func5\n' + nested), [0x04, 0x10, 0x05, 0x10, 4, 5])

    def testOptionalMessages(self):
        """An optional block needs an .end, and its symbols are not defined when it is left out."""
        self._assertMessages([
            ('.optional\n'
             't: nop\n', 'test.asm:1: error: Optional without matching end'),
            ('.optional\n'
             'f: nop\n'
             '.optional\n'
             'g: nop\n'
             '.end\n'
             '.end\n'
             'jmp g\n',  "test.asm:7: error: Name 'g' is not defined"),
            ('.optional\n'
             'f: nop\n'
             'K = 2\n'
             '.end\n'
             'lda #K\n', "test.asm:5: error: Name 'K' is not defined"),
        ])

    def testOperatorsNextToOperands(self):
        """Number prefixes and local labels work next to any operator, without spaces."""
        for source, expected in [
            ('t = $20\n'
             'lda t-$10\n',    [0xa5, 0x10]),
            ('.byte -$10\n',   [0xf0]),             # two's complement
            ('.byte 2*$10\n',  [0x20]),
            ('.byte 8-%10\n',  [6]),                # 8 - 2
            ('.byte %101%2\n', [1]),                # 5 % 2
            ('.byte 7%$10\n',  [7]),                # 7 % 16
            ('x =.5\n'
             '.byte x*2\n',    [1]),                # .5 right after =
            ('g:\n'
             '_a: nop\n'
             '_b: nop\n'
             '.byte _b-_a\n',  [0xea, 0xea, 1]),
            ('g:\n'
             '_a: nop\n'
             '.word 2*_a\n',   [0xea, 0x00, 0x20]), # 2 * $1000
            ('nop\n'
             '.word _-1\n',    [0xea, 0x00, 0x10]), # the current address, $1001, less 1
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._memory(source), expected)

    def testSection(self):
        """A section starts at its address, and continues where it stopped."""
        for source, expected in [
            ('.section "a", $2000\n'
             '.byte 1\n'
             '.section "b", $3000\n'
             '.byte 2\n'
             '.section "a"\n'
             '.byte 3\n',    {0x2000: 1, 0x2001: 3, 0x3000: 2}),
            ('.section "a", 0\n'
             '.byte 1\n'
             '.section "b", $1000\n'
             '.byte 2\n'
             '.section "a"\n'
             '.byte 3\n',    {0: 1, 1: 3, 0x1000: 2}), # address 0
            ('.section "a", $2000\n'
             '.org $2800\n'
             '.byte 1\n'
             '.section "b", $3000\n'
             '.section "a"\n'
             '.byte 2\n',    {0x2800: 1, 0x2801: 2}),  # .org in a section
            ('.section "a", $2000\n'
             '.word b\n'
             '.section "b", $3000\n'
             'b: .byte 1\n', {0x2000: 0, 0x2001: 0x30, 0x3000: 1}), # a forward reference
            ('.section "a", $2000\n'
             '_ = _ + 1\n'
             '.section "b", $3000\n'
             '.section "a"\n'
             '.byte 1\n',    {0x2001: 1}),             # memory reserved, nothing stored
            ('.section "a", $2000\n'
             'g: nop\n'
             '_x: nop\n'
             '.section "b", $3000\n'
             '.word _x\n',   {0x2000: 0xea, 0x2001: 0xea, 0x3000: 1, 0x3001: 0x20}), # local labels don't change
            ('.byte 1\n'
             '.section "a", $2000\n'
             '.byte 2\n',    {0x1000: 1, 0x2000: 2}),  # code before the first section
        ]:
            with self.subTest(source=source):
                context = self._assembleForTarget(source)
                self.assertEqual(context.errors, [])
                self.assertEqual(context.memory, expected)

    def testSectionMessages(self):
        """A new section needs an address, and only a new section can have one."""
        self._assertMessages([
            ('.section "x"\n',        'test.asm:1: error: New section needs an address: "x"'),
            ('.section "x", $1000\n'
             '.section "x", $2000\n', 'test.asm:2: error: Section already has an address: "x"'),
            ('.section "x", $1000\n'
             '.section "y", $2000\n'
             '.section "x", $3000\n', 'test.asm:3: error: Section already has an address: "x"'),
            ('.section 5, $1000\n',   'test.asm:1: error: Invalid directive: .section 5,0x1000'),
            ('.section\n',            'test.asm:1: error: Invalid directive: .section'),
            ('.section "a", $1000\n'
             '.byte 1, 1, 1\n'
             '.section "b", $1002\n'
             '.byte 2\n',             'test.asm:4: warning: $1002 is overwritten ($01 to $02)'),
        ])

    def testSectionInImportedFile(self):
        """An imported file continues the sections of the file that imports it."""
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, 'lib.asm'), 'w') as f:
                f.write('.section "code"\n'
                        '.byte 2\n'
                        '.section "data"\n'
                        '.byte 4\n')
            filename = os.path.join(directory, 'test.asm')
            with open(filename, 'w') as f:
                f.write('.section "data", $2000\n'
                        '.section "code", $1000\n'
                        '.byte 1\n'
                        '.import "lib.asm"\n'
                        '.section "code"\n'
                        '.byte 3\n'
                        '.section "data"\n'
                        '.byte 5\n')
            context = assembleFile(filename)
        self.assertEqual(context.errors, [])
        self.assertEqual(context.memory, {0x1000: 1, 0x1001: 2, 0x1002: 3, 0x2000: 4, 0x2001: 5})

    def testZeroPageMessages(self):
        """zp() needs a positive int as the size, and the zero page has 254 bytes, from $02 to $ff."""
        self._assertMessages([
            ('a = zp(0)\n',    'test.asm:1: error: Zero page size must be positive: "zp(0)"'),
            ('a = zp(1.5)\n',  'test.asm:1: error: Zero page size must be an int, not float: "zp(1.5)"'),
            ('a = zp("x")\n',  'test.asm:1: error: Zero page size must be an int, not str: "zp(f"x")"'),
            ('a = zp(True)\n', 'test.asm:1: error: Zero page size must be an int, not bool: "zp(True)"'),
            ('a = zp(255)\n',  'test.asm:1: error: Not enough zero page left: 255 needed, 254 left: "zp(255)"'),
            ('a = zp(254)\n'
             'b = zp(1)\n',    'test.asm:2: error: Not enough zero page left: 1 needed, 0 left: "zp(1)"'),
        ])

    def testZeroPageReused(self):
        """Each zp() allocates new bytes, also for a name that has some, or in a loop. A name holds its latest address,
        and a use before its first assignment gets the last one."""
        for source, expected in [
            ('lda temp\n'
             'temp = zp(1)\n'
             'sta temp\n'
             'temp = zp(1)\n'
             'sta temp\n',      [0xa5, 0x03, 0x85, 0x02, 0x85, 0x03]), # temp before its first assignment is the last one, $03
            ('.repeat 3\n'
             'v = zp(1)\n'
             '.end\n'
             'next = zp(1)\n'
             '.byte next, v\n', [0x05, 0x04]),                         # $02 to $04 in the loop
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._memory(source), expected)

    def testPrint(self):
        """.print prints once, after the last pass, so values are final, even with errors."""
        anyErrors, output = self._assemble('.print "start", later\n'
                                           'jmp later\n'
                                           'later: rts\n') # later is $1003
        self.assertFalse(anyErrors, output)
        self.assertEqual(output.count('start\n'), 1, output)
        self.assertIn('start\n4099\n', output)
        anyErrors, output = self._assemble('.print "before"\n'
                                           '.error "stop"\n')
        self.assertTrue(anyErrors)
        self.assertIn('before\n', output)

    def testAssert(self):
        """.assert reports nothing if the condition is true, also for labels defined later."""
        for source in ['.assert 2 < 3\n', '.assert 2 < 3, "Something is wrong"\n',
                       '.assert later == $1003\n'
                       'jmp later\n'
                       'later: rts\n']:
            with self.subTest(source=source):
                anyErrors, output = self._assemble(source)
                self.assertFalse(anyErrors, output)

    def testBreak(self):
        """.break collects a breakpoint at the current address, with an optional VICE condition."""
        with tempfile.TemporaryDirectory() as directory:
            filename = os.path.join(directory, 'test.asm')
            with open(filename, 'w') as f:
                f.write('nop\n'
                        '.break\n'
                        'nop\n'
                        '.break "RL > $40 && A == $00"\n'
                        'later: rts\n'
                        '.break 5\n')
            context = assembleFile(filename)
        self.assertEqual(context.breakpoints, [(0x1001, None), (0x1002, 'RL > $40 && A == $00')])
        self.assertEqual([e.split('/')[-1] for e in context.errors], ['test.asm:6: error: Invalid directive: .break 5']) # without the folder

    def _assembleForTarget(self, source: str, target: str | None = None) -> Context:
        """Assemble source for the target, and return the context."""
        with tempfile.TemporaryDirectory() as directory:
            filename = os.path.join(directory, 'test.asm')
            with open(filename, 'w') as f:
                f.write(source)
            return assembleFile(filename, target=target)

    def testNoTarget(self):
        """Without a target only the generic 6502 imports are available, and no BASIC."""
        self.assertEqual(self._assembleForTarget('@ldax($1234)\n'
                                                 '@pushRegisters()\n'
                                                 'lda INTERRUPT_VECTOR_NMI\n').errors, [])
        for name in ['VIC_BORDER_COLOR', 'KERNAL_ROM', 'BASIC_START_ADDRESS', 'BASIC_TOKEN_SYS', 'basic', 'CHAR_ROM', 'IO_PORT_DATA']:
            with self.subTest(name=name):
                self.assertIn(f"Name '{name}' is not defined", self._assembleForTarget(f'.word {name}\n').errors[0])

    def testBasicVersions(self):
        """Each target has the BASIC version of its machine: its tokens, and the keywords @basic.line converts."""
        for target, graphic in [('c64', None), ('vic20', None), ('c16', 0xde), ('plus4', 0xde), ('c128', 0xde), ('cx16', None)]:
            with self.subTest(target=target):
                context = self._assembleForTarget('.org $1000\n'
                                                  '@basic.line(10, "GRAPHIC 1")\n', target)
                self.assertEqual(context.errors, [])
                self.assertEqual(context.symbols.get('BASIC_TOKEN_GRAPHIC'), graphic)
                self.assertEqual(context.memory[0x1004], graphic or ord('G')) # the text, after the link and the line number
        context = self._assembleForTarget('.org $1000\n'
                                          '@basic.line(10, "BANK 15")\n', 'c128') # BASIC 7.0, not 3.5
        self.assertEqual([context.memory[0x1004], context.memory[0x1005]], [0xfe, 0x02])

    def testBasicLineProgram(self):
        """Each line links to the next, labels can be used, and the text encoding is unchanged."""
        memory = self._memory('.org $1001\n'
                              '@basic.line(10, "SYS {start}")\n'
                              '@basic.line(20, "END")\n'
                              '@basic.end()\n'
                              'start: .text "A"\n', 'c64')
        self.assertEqual(memory[:2], [0x0c, 0x10])                     # 2 + 2 + 7 bytes of text and the end, from $1001
        self.assertEqual(memory[4:11], [0x9e, *b' 4116', 0])           # start is $1014
        self.assertEqual(memory[11:13], [0x12, 0x10])                  # the next line, at $100c
        self.assertEqual(memory[-1], 1)                                # a screen code, the default

    def testBasicSys(self):
        """@basic.sys is a @basic.line with a SYS, so it has the same link to the next line, and text encoding."""
        memory = self._memory('.org $1001\n'
                              '@basic.sys(10, start)\n'
                              '@basic.end()\n'
                              'start: .text "A"\n', 'c64')
        self.assertEqual(memory, [0x0b, 0x10, 10, 0, 0x9e, *b'4109', 0, 0, 0, 1]) # the link to $100b, line 10, SYS 4109 ($100d), the ends of the line and program, and A

    def testBasicInNamespace(self):
        """basic is a built-in symbol, so code in a namespace can use its generators too."""
        with tempfile.TemporaryDirectory() as directory:
            for name, source in [('test.asm', '.org $1001\n'
                                              '.import "boot.asm", "spr"\n'
                                              '@basic.end()\n'),
                                 ('boot.asm', '@basic.line(10, "END")\n')]:
                with open(os.path.join(directory, name), 'w') as f:
                    f.write(source)
            context = assembleFile(os.path.join(directory, 'test.asm'), target='c64')
        self.assertEqual(context.errors, [])
        self.assertEqual([context.memory[address] for address in sorted(context.memory)], [0x07, 0x10, 10, 0, 0x80, 0, 0, 0]) # END is $80

    def testBasicFloat(self):
        """@basic.float stores a number in BASIC's 5-byte floating point format: the exponent, biased by 128, and
        4 bytes of the mantissa, with the sign in its top bit. Several values are constants in the C64's BASIC ROM."""
        for number, expected in [
            ('0',          [0x00, 0x00, 0x00, 0x00, 0x00]), # zero has exponent 0
            ('1',          [0x81, 0x00, 0x00, 0x00, 0x00]),
            ('-1',         [0x81, 0x80, 0x00, 0x00, 0x00]), # the sign bit set
            ('0.5',        [0x80, 0x00, 0x00, 0x00, 0x00]), # 0.5, in the ROM at $bf11
            ('0.25',       [0x7f, 0x00, 0x00, 0x00, 0x00]),
            ('10',         [0x84, 0x20, 0x00, 0x00, 0x00]), # 10, in the ROM at $baf9
            ('-32768',     [0x90, 0x80, 0x00, 0x00, 0x00]), # -32768, in the ROM at $b1a5
            ('sqrt(0.5)',  [0x80, 0x35, 0x04, 0xf3, 0x34]), # SQR(0.5), in the ROM at $e2e5, rounded to the nearest
            ('pi',         [0x82, 0x49, 0x0f, 0xda, 0xa2]),
            ('1.7e38',     [0xff, 0x7f, 0xc9, 0x9e, 0x3c]), # near the largest
            ('1 - 2**-40', [0x81, 0x00, 0x00, 0x00, 0x00]), # rounded up to 1
            ('1e-39',      [0x00, 0x00, 0x00, 0x00, 0x00]), # too small, so zero, as in BASIC
        ]:
            with self.subTest(number=number):
                self.assertEqual(self._memory(f'@basic.float({number})\n', 'c64'), expected)

    def testBasicFloatMessages(self):
        """A number too large for BASIC is an error."""
        self.assertIn('test.asm:1: error: Too large for a BASIC float: 1e+39', self._assembleForTarget('@basic.float(1e39)\n', 'c64').errors[0])

    def _assembleFiles(self, files: dict, target: str) -> Context:
        """Assemble test.asm for the target, with the other files {name: text} beside it, and return the context."""
        with tempfile.TemporaryDirectory() as directory:
            for name, text in files.items():
                with open(os.path.join(directory, name), 'w') as f:
                    f.write(text)
            return assembleFile(os.path.join(directory, 'test.asm'), target=target)

    def testBasicLoad(self):
        """@basic.load writes the lines of a BASIC listing as @basic.line does, with {expression} filled in, skipping
        blank lines. The file is beside the main source file."""
        loaded = self._assembleFiles({'test.asm': '@basic.start()\n'
                                                  '@basic.load("menu.bas")\n'
                                                  '@basic.end()\n'
                                                  'start: rts\n',
                                      'menu.bas': '10 POKE 53280,0\n'
                                                  '\n'
                                                  '20 PRINT "HELLO"\n'
                                                  '  30   SYS {start}  \n'}, 'c64') # spaces around the line number and text
        written = self._assembleFiles({'test.asm': '@basic.start()\n'
                                                   '@basic.line(10, "POKE 53280,0")\n'
                                                   '@basic.line(20, \'PRINT "HELLO"\')\n'
                                                   '@basic.line(30, "SYS {start}")\n'
                                                   '@basic.end()\n'
                                                   'start: rts\n'}, 'c64')
        self.assertEqual(loaded.errors, [])
        self.assertEqual(loaded.memory, written.memory)

    def testBasicLoadMessages(self):
        """A file that isn't found, or a line without a line number, is an error."""
        for files, message in [
            ({'test.asm': '@basic.load("nothere.bas")\n'},  'test.asm:1: error: File not found: "nothere.bas"'),
            ({'test.asm': '@basic.load("menu.bas")\n',
              'menu.bas': '10 PRINT 1\n'
                          'PRINT 2\n'},                       'test.asm:1: error: Line 2 of "menu.bas" has no line number: "PRINT 2"'),
        ]:
            with self.subTest(files=files):
                errors = self._assembleFiles(files, 'c64').errors
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(message, errors[0])

    def testBasicLineMessages(self):
        """Text that BASIC can't store is an error."""
        self.assertIn("test.asm:1: error: 'ascii' codec can't encode", self._assembleForTarget('@basic.line(10, "PRINT \\"é\\"")\n', 'c64').errors[0])

    def testDefines(self):
        """Defines are assigned before the source in each pass: upper case names are constants, lower case names variables."""
        def assembleWithDefines(source: str, defines: dict) -> Context:
            """Assemble source with the defines, and return the context."""
            with tempfile.TemporaryDirectory() as directory:
                filename = os.path.join(directory, 'test.asm')
                with open(filename, 'w') as f:
                    f.write(source)
                return assembleFile(filename, defines=defines)
        context = assembleWithDefines('.byte PAL, size\n'
                                      'size = 2\n'
                                      '.if DEBUG\n'
                                      '.byte 3\n'
                                      '.end\n', {'PAL': '1', 'size': '$10', 'DEBUG': 'True'})
        self.assertEqual(context.errors, [])
        self.assertEqual(context.memory, {0x1000: 1, 0x1001: 0x10, 0x1002: 3}) # size is $10 again in each pass
        self.assertEqual(assembleWithDefines('PAL = 1\n', {'PAL': '1'}).errors, [])   # the same value
        self.assertIn('error: Constant "PAL" cannot be changed from 1 to 2', assembleWithDefines('PAL = 2\n', {'PAL': '1'}).errors[0])
        self.assertEqual(assembleWithDefines('nop\n', {'X': 'unknown'}).errors,
                         ['<command-line>:1: error: Name \'unknown\' is not defined: "unknown"'])

    def testTargets(self):
        """A target adds the imports of its folder, to the generic ones."""
        source = ('@basic.start()\n'
                  '@basic.line(10, "SYS {start}")\n'
                  '@basic.end()\n'
                  'start: @ldax($1234)\n')
        for target, start in [('c64', 0x0801), ('vic20', 0x1001), ('c16', 0x1001), ('plus4', 0x1001), ('c128', 0x1c01), ('cx16', 0x0801)]:
            with self.subTest(target=target):
                context = self._assembleForTarget(source, target)
                self.assertEqual(context.errors, [])
                self.assertEqual(min(context.memory), start)
                self.assertEqual(context.symbols['BASIC_START_ADDRESS'], start)
        self.assertEqual(self._assembleForTarget('.word VIC_BORDER_COLOR, CHAR_ROM\n', 'c64').errors, [])
        symbols = self._assembleForTarget('nop\n', 'c64').symbols
        self.assertNotIn('VIC_KEYBOARD', symbols)                      # the C128's VIC registers are not on the C64
        self.assertNotIn('VIC_2MHZ_MODE', symbols)

    def testVic20Vic(self):
        """The VIC-20 has its own VIC registers and colors, also where the name is the same as on the C64."""
        symbols = self._assembleForTarget('nop\n', 'vic20').symbols
        for name, value in [('VIC_ORIGIN_X', 0x9000), ('VIC_ORIGIN_Y', 0x9001), ('VIC_COLUMNS', 0x9002), ('VIC_ROWS', 0x9003),
                            ('VIC_RASTER_COUNTER', 0x9004), ('VIC_MEMORY_POINTERS', 0x9005),
                            ('VIC_LIGHT_PEN_X', 0x9006), ('VIC_LIGHT_PEN_Y', 0x9007), ('VIC_PADDLE_X', 0x9008), ('VIC_PADDLE_Y', 0x9009),
                            ('VIC_OSCILLATOR1', 0x900a), ('VIC_OSCILLATOR2', 0x900b), ('VIC_OSCILLATOR3', 0x900c), ('VIC_NOISE', 0x900d),
                            ('VIC_AUXILIARY_COLOR_VOLUME', 0x900e), ('VIC_BACKGROUND_BORDER_COLOR', 0x900f),
                            ('VIC_COLOR_BLACK', 0), ('VIC_COLOR_YELLOW', 7), ('VIC_COLOR_ORANGE', 8), ('VIC_COLOR_LIGHT_YELLOW', 15)]:
            with self.subTest(name=name):
                self.assertEqual(symbols[name], value)
        self.assertEqual(self._assembleForTarget('nop\n', 'c64').symbols['VIC_RASTER_COUNTER'], 0xd012)
        self.assertIn("Name 'VIC_BORDER_COLOR' is not defined", self._assembleForTarget('.word VIC_BORDER_COLOR\n', 'vic20').errors[0])
        self.assertIn("Name 'VIC_ORIGIN_X' is not defined", self._assembleForTarget('.word VIC_ORIGIN_X\n', 'c16').errors[0])

    def testVic20Via(self):
        """The VIC-20 has two VIA chips, with the same registers from $9110 and $9120."""
        symbols = self._assembleForTarget('nop\n', 'vic20').symbols
        registers = ['DATA_PORTB', 'DATA_PORTA', 'DATA_DIRECTION_PORTB', 'DATA_DIRECTION_PORTA',
                     'TIMER1_COUNTER_LO', 'TIMER1_COUNTER_HI', 'TIMER1_LATCH_LO', 'TIMER1_LATCH_HI', 'TIMER2_LO', 'TIMER2_HI',
                     'SERIAL_SHIFT', 'AUXILIARY_CONTROL', 'PERIPHERAL_CONTROL', 'INTERRUPT_FLAG', 'INTERRUPT_ENABLE', 'DATA_PORTA_NO_HANDSHAKE']
        for chip, base in [('VIA1', 0x9110), ('VIA2', 0x9120)]:
            for offset, register in enumerate(registers):
                with self.subTest(register=f'{chip}_{register}'):
                    self.assertEqual(symbols[f'{chip}_{register}'], base + offset)
        self.assertIn("Name 'VIA1_DATA_PORTA' is not defined", self._assembleForTarget('.word VIA1_DATA_PORTA\n', 'c64').errors[0])

    def testVic20Machine(self):
        """The screen and color RAM of the VIC-20, without and with 8K or more of memory expansion."""
        symbols = self._assembleForTarget('nop\n', 'vic20').symbols
        for name, value in [('SCREEN_RAM', 0x1e00), ('COLOR_RAM', 0x9600), ('SCREEN_RAM_EXPANDED', 0x1000), ('COLOR_RAM_EXPANDED', 0x9400)]:
            with self.subTest(name=name):
                self.assertEqual(symbols[name], value)
        self.assertIn("Name 'SCREEN_RAM' is not defined", self._assembleForTarget('.word SCREEN_RAM\n', 'c64').errors[0])

    def testC16Ted(self):
        """The C16 has the TED registers and colors, and only there."""
        symbols = self._assembleForTarget('nop\n', 'c16').symbols
        for name, value in [('TED_TIMER1_LO', 0xff00), ('TED_TIMER3_HI', 0xff05), ('TED_CONTROL_SCROLL_Y', 0xff06), ('TED_CONTROL_SCROLL_X', 0xff07),
                            ('TED_KEYBOARD', 0xff08), ('TED_INTERRUPT_REGISTER', 0xff09), ('TED_INTERRUPT_ENABLED', 0xff0a), ('TED_RASTER_COMPARE', 0xff0b),
                            ('TED_CURSOR_HI', 0xff0c), ('TED_CURSOR_LO', 0xff0d),
                            ('TED_VOICE1_FREQUENCY_LO', 0xff0e), ('TED_VOICE2_FREQUENCY_LO', 0xff0f), ('TED_VOICE2_FREQUENCY_HI', 0xff10),
                            ('TED_SOUND_CONTROL', 0xff11), ('TED_VOICE1_FREQUENCY_HI', 0xff12), ('TED_CHARSET', 0xff13), ('TED_SCREEN', 0xff14),
                            ('TED_BACKGROUND_COLOR0', 0xff15), ('TED_BACKGROUND_COLOR3', 0xff18), ('TED_BORDER_COLOR', 0xff19),
                            ('TED_CHARACTER_POSITION_HI', 0xff1a), ('TED_CHARACTER_POSITION_LO', 0xff1b), ('TED_RASTER_HI', 0xff1c), ('TED_RASTER_LO', 0xff1d),
                            ('TED_HORIZONTAL_POSITION', 0xff1e), ('TED_CHARACTER_LINE_FLASH', 0xff1f), ('TED_ROM_SELECT', 0xff3e), ('TED_RAM_SELECT', 0xff3f),
                            ('TED_COLOR_BLACK', 0), ('TED_COLOR_YELLOW', 7), ('TED_COLOR_LIGHT_GREEN', 15)]:
            with self.subTest(name=name):
                self.assertEqual(symbols[name], value)
        self.assertEqual(symbols['tedColor'](symbols['TED_COLOR_RED'], 5), 0x52) # luminance 5 in the high nibble, and red, 2
        self.assertIn("Name 'TED_BORDER_COLOR' is not defined", self._assembleForTarget('.word TED_BORDER_COLOR\n', 'c64').errors[0])

    def testKernal(self):
        """The KERNAL routines of each target, from their jump tables, which mostly have the same addresses."""
        routines = ['RESTOR', 'VECTOR', 'SETMSG', 'LSTNSA', 'TALKSA', 'MEMBOT', 'MEMTOP', 'SCNKEY', 'SETTMO', 'IECIN', 'IECOUT', 'UNTALK',
                    'UNLSTN', 'LISTEN', 'TALK', 'READST', 'SETLFS', 'SETNAM', 'OPEN', 'CLOSE', 'CHKIN', 'CHKOUT', 'CLRCHN', 'CHRIN', 'CHROUT',
                    'LOAD', 'SAVE', 'SETTIM', 'RDTIM', 'STOP', 'GETIN', 'CLALL', 'UDTIM', 'SCREEN', 'PLOT', 'IOBASE']
        symbols = {target: self._assembleForTarget('nop\n', target).symbols for target in TARGETS}
        for routine in routines:
            with self.subTest(routine=routine):
                addresses = {target: symbols[target][f'KERNAL_ROM_{routine}'] for target in TARGETS}
                self.assertEqual(len(set(addresses.values())), 1, addresses)
        self.assertEqual(symbols['c16']['KERNAL_ROM_CHROUT'], 0xffd2)
        self.assertEqual((symbols['c64']['KERNAL_ROM_MEMTOP'], symbols['c64']['KERNAL_ROM_MEMBOT']), (0xff99, 0xff9c))
        self.assertEqual({target: symbols[target]['KERNAL_ROM'] for target in TARGETS},
                         {'c64': 0xe000, 'vic20': 0xe000, 'c16': 0xc000, 'plus4': 0xc000, 'c128': 0xc000, 'cx16': 0xc000})
        self.assertEqual({symbols['c16']['KERNAL_ROM_SCINIT'], symbols['c16']['KERNAL_ROM_IOINIT'], symbols['c16']['KERNAL_ROM_RAMTAS']}, {0xff81, 0xff84, 0xff87})
        self.assertNotIn('KERNAL_ROM_SCINIT', symbols['vic20'])                # the VIC-20 table starts at $ff8a

    def testC16Machine(self):
        """The screen and color RAM of the C16."""
        symbols = self._assembleForTarget('nop\n', 'c16').symbols
        self.assertEqual((symbols['SCREEN_RAM'], symbols['COLOR_RAM']), (0x0c00, 0x0800))

    def testC128(self):
        """The C128 has the chips of the C64, its own memory addresses, the MMU and the VDC."""
        symbols = self._assembleForTarget('nop\n', 'c128').symbols
        for name, value in [('VIC_BORDER_COLOR', 0xd020), ('SID_VOICE1_FREQUENCY_LO', 0xd400), ('CIA1_DATA_PORTA', 0xdc00), ('SCREEN_RAM', 0x0400),
                            ('COLOR_RAM', 0xd800), ('MMU_CONFIGURATION', 0xd500), ('MMU_VERSION', 0xd50b), ('VDC_ADDRESS', 0xd600), ('VDC_DATA', 0xd601)]:
            with self.subTest(name=name):
                self.assertEqual(symbols[name], value)
        self.assertEqual((symbols['VIC_KEYBOARD'], symbols['VIC_2MHZ_MODE']), (0xd02f, 0xd030))

    def testPlus4(self):
        """The Plus/4 has the same symbols as the C16, and no SID."""
        symbols = {target: self._assembleForTarget('nop\n', target).symbols for target in ['c16', 'plus4']}
        for name, value in symbols['c16'].items():
            if name.isupper() and name != 'SOURCE_FOLDER': # the folder of the source: a new temporary folder for each
                with self.subTest(name=name):
                    self.assertEqual(symbols['plus4'][name], value)
        self.assertEqual(symbols['plus4']['TED_BORDER_COLOR'], 0xff19)

    def testCx16(self):
        """The Commander X16: the bank registers and windows, the ROM banks, zero page, the VIAs, VERA and its VRAM, and the YM2151."""
        symbols = self._assembleForTarget('nop\n', 'cx16').symbols
        for name, value in [('RAM_BANK', 0x00), ('ROM_BANK', 0x01), ('BANKED_RAM', 0xa000), ('BANKED_ROM', 0xc000),
                            ('ROM_BANK_KERNAL', 0), ('ROM_BANK_BASIC', 4), ('ROM_BANK_BASLOAD', 15),
                            ('ZERO_PAGE_USER', 0x22), ('ZERO_PAGE_USER_END', 0x7f), ('KERNAL_R0', 0x02), ('KERNAL_R15', 0x20),
                            ('KERNAL_ROM_SCINIT', 0xff81), ('VIA1_DATA_PORTB', 0x9f00), ('VIA2_INTERRUPT_ENABLE', 0x9f1e),
                            ('VERA_ADDRESS_LO', 0x9f20), ('VERA_DATA0', 0x9f23), ('VERA_CONTROL', 0x9f25), ('VERA_IRQ_LINE', 0x9f28),
                            ('VERA_SCAN_LINE', 0x9f28), ('VERA_BORDER_COLOR', 0x9f2c), ('VERA_VERTICAL_STOP', 0x9f2c), # by VERA_CONTROL's DC select
                            ('VERA_LAYER0_CONFIG', 0x9f2d), ('VERA_LAYER1_CONFIG', 0x9f34), ('VERA_LAYER1_VSCROLL_HI', 0x9f3a),
                            ('VERA_SPI_CONTROL', 0x9f3f), ('VERA_VRAM_TEXT', 0x1b000), ('VERA_VRAM_PSG', 0x1f9c0),
                            ('VERA_VRAM_PALETTE', 0x1fa00), ('VERA_VRAM_SPRITES', 0x1fc00), ('YM2151_ADDRESS', 0x9f40), ('YM2151_DATA', 0x9f41),
                            ('YM2151_REGISTER_KEY_ON', 0x08), ('YM2151_REGISTER_TIMER_B', 0x12), ('YM2151_REGISTER_KEY_CODE', 0x28),
                            ('YM2151_REGISTER_TOTAL_LEVEL', 0x60), ('YM2151_REGISTER_DECAY1_LEVEL_RELEASE', 0xe0)]:
            with self.subTest(name=name):
                self.assertEqual(symbols[name], value)
        self.assertNotIn('VIC_BORDER_COLOR', symbols)

    def testTargetOnlyHasItsOwnImports(self):
        """The imports of one target are not available in another."""
        for target in ['vic20', 'c16', 'cx16']:
            with self.subTest(target=target):
                self.assertIn("Name 'SID_", self._assembleForTarget('.word SID_VOICE1_FREQUENCY_LO\n', target).errors[0])

    def testUnknownTarget(self):
        """A target without a folder is an error."""
        with self.assertRaises(ValueError) as raised:
            self._assembleForTarget('nop\n', 'amiga')
        self.assertEqual(str(raised.exception), 'Unknown target: amiga')

    def testBrokenBuiltinImport(self):
        """A built-in import that fails raises its exception, with the import file in the traceback."""
        from unittest import mock
        import traceback
        with tempfile.TemporaryDirectory() as directory:
            filename = os.path.join(directory, 'broken.py')
            with open(filename, 'w') as f:
                f.write('1/0\n')
            with mock.patch('glob.glob', return_value=[filename]): # instead of the imports folder
                try:
                    self._assemble('nop\n')
                    self.fail('ZeroDivisionError not raised')
                except ZeroDivisionError as exception: # not assertRaises, which drops the traceback
                    self.assertEqual(traceback.extract_tb(exception.__traceback__)[-1].filename, filename)


class TestMusic(unittest.TestCase):
    """Tests of reading SID files."""

    def setUp(self):
        """Create a temporary folder for the SID files."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = directory.name
        self._Music = self._assemble('nop\n').symbols.get('_Music') # the Music class of music.py

    def _sidFile(self, magicId=b'PSID', version=2, dataOffset=None, loadAddress=0x1000, initAddress=0x1000, playAddress=0x1003,
                 songs=1, startSong=1, speed=0, name=b'', author=b'', released=b'',
                 flags=0, startPage=0, pageLength=0, secondSid=0, thirdSid=0, data=b'\x4c\x00\x10\x60') -> str:
        """Write a SID file, with the header of the version, and return its name."""
        if dataOffset is None:
            dataOffset = 0x76 if version == 1 else 0x7c # the header size of version 1, and of the later versions
        header = struct.pack('>4sHHHHHHHL32s32s32s', magicId, version, dataOffset, loadAddress, initAddress, playAddress,
                             songs, startSong, speed, name, author, released)
        if version >= 2:
            header += struct.pack('>HBBBB', flags, startPage, pageLength, secondSid, thirdSid)
        filename = os.path.join(self.directory, f'{len(os.listdir(self.directory))}.sid')
        with open(filename, 'wb') as f:
            f.write(header[:dataOffset] + data) # a smaller data offset cuts the header short
        return filename

    def _load(self, filename: str):
        """Load the file, and return the Music, or None, and the errors."""
        try:
            return self._Music.load(filename), []
        except ValueError as exception:
            return None, [str(exception)]

    def _assemble(self, source: str, target: str = 'c64') -> Context:
        """Assemble source in the temporary folder, and return the context."""
        filename = os.path.join(self.directory, 'test.asm')
        with open(filename, 'w') as f:
            f.write(source)
        return assembleFile(filename, target=target)

    def testImportMusic(self):
        """@importMusic stores the music where .org says, and defines the addresses with the prefix."""
        sid = os.path.basename(self._sidFile(loadAddress=0x2000, initAddress=0x2000, playAddress=0x2003, data=b'\x4c\x00\x20\x60'))
        context = self._assemble('.org MUSIC_LOAD\n'
                                 f'@importMusic("{sid}", "MUSIC")\n'
                                 'jsr MUSIC_INIT\n')
        self.assertEqual(context.errors, [])
        memory = [context.memory[address] for address in sorted(context.memory)]
        self.assertEqual(memory, [0x4c, 0x00, 0x20, 0x60, 0x20, 0x00, 0x20]) # the music, and jsr MUSIC_INIT
        self.assertEqual(min(context.memory), 0x2000)
        symbols = context.symbols
        self.assertEqual((symbols['MUSIC_LOAD'], symbols['MUSIC_INIT'], symbols['MUSIC_PLAY']), (0x2000, 0x2000, 0x2003))

    def testImportMusicWithLoadAddressInData(self):
        """The load address in the first two bytes of the data is not stored."""
        sid = os.path.basename(self._sidFile(loadAddress=0, initAddress=0x2000, data=b'\x00\x20\x60'))
        context = self._assemble('.org M_LOAD\n'
                                 f'@importMusic("{sid}", "M")\n')
        self.assertEqual(context.errors, [])
        self.assertEqual(context.memory, {0x2000: 0x60})

    def testImportMusicMessages(self):
        """A file that is not found or not valid is an error, and the generator needs the c64 target."""
        sid = os.path.basename(self._sidFile(magicId=b'MSID'))
        for source, target, message in [
            ('@importMusic("nothere.sid", "M")\n', 'c64',   'test.asm:1: error: File not found: "nothere.sid"'),
            (f'@importMusic("{sid}", "M")\n',      'c64',   f'test.asm:1: error: Not a valid sid file: "{sid}": not PSID or RSID'),
            (f'@importMusic("{sid}", "M")\n',      None,    "test.asm:1: error: Name 'importMusic' is not defined"),
            (f'@importMusic("{sid}", "M")\n',      'vic20', "test.asm:1: error: Name 'importMusic' is not defined"),
            (f'.music "{sid}", "M"\n',             'c64',   'test.asm:1: error: Invalid directive: .music'),
        ]:
            with self.subTest(source=source, target=target):
                self.assertIn(message, '\n'.join(self._assemble(source, target).errors).replace(self.directory + os.sep, ''))

    def testImportsAreNotSymbols(self):
        """The class and the Python modules in music.py don't take names from the source."""
        symbols = self._assemble('nop\n').symbols
        for name in ['Music', 'os', 'struct', 'dataclass', 'field']:
            with self.subTest(name=name):
                self.assertNotIn(name, symbols)

    def testPsidVersion1(self):
        """Version 1 has the shorter header, and no flags."""
        music, errors = self._load(self._sidFile(version=1, songs=3, startSong=2, name=b'Song', author=b'Me', released=b'2021 Me'))
        self.assertEqual(errors, [])
        self.assertEqual((music.magicId, music.version), ('PSID', 1))
        self.assertEqual((music.loadAddress, music.initAddress, music.playAddress), (0x1000, 0x1000, 0x1003))
        self.assertEqual(music.data, b'\x4c\x00\x10\x60')
        self.assertEqual((music.songs, music.startSong), (3, 2))
        self.assertEqual((music.name, music.author, music.released), ('Song', 'Me', '2021 Me'))
        self.assertEqual((music.flags, music.clock, music.sidModels, music.sidAddresses), (0, 'unknown', ['unknown'], [0xd400]))

    def testLoadAddressInData(self):
        """A load address of 0 means the first two bytes of the data are the load address."""
        music, errors = self._load(self._sidFile(loadAddress=0, data=b'\x00\x20\x60'))
        self.assertEqual(errors, [])
        self.assertEqual((music.loadAddress, music.data), (0x2000, b'\x60'))

    def testInitAddressDefault(self):
        """An init address of 0 means the load address."""
        music, errors = self._load(self._sidFile(loadAddress=0x1800, initAddress=0))
        self.assertEqual(music.initAddress, 0x1800)

    def testPsidVersion2(self):
        """Version 2 adds the flags and the relocation range. Strings are Latin-1, and can fill all 32 bytes."""
        flags = 0b01 << 2 | 0b10 << 4 # PAL, MOS8580
        music, errors = self._load(self._sidFile(flags=flags, startPage=0x20, pageLength=0x10, name=b'J\xe4ger' + b'x'*27, author=b'A'*32))
        self.assertEqual(errors, [])
        self.assertEqual((music.clock, music.sidModels, music.isBasic, music.isPlaySidSpecific), ('PAL', ['MOS8580'], False, False))
        self.assertEqual((music.startPage, music.pageLength), (0x20, 0x10))
        self.assertEqual((music.name, music.author), ('Jäger' + 'x'*27, 'A'*32))
        music, errors = self._load(self._sidFile(flags=0b11 << 2 | 0b11 << 4 | 0b10)) # PAL and NTSC, both SID models, PlaySID specific
        self.assertEqual((music.clock, music.sidModels, music.isPlaySidSpecific), ('PAL and NTSC', ['MOS6581 and MOS8580'], True))

    def testExtraSids(self):
        """Version 3 adds a second SID, and version 4 a third, each with its own model and address."""
        flags = 0b01 << 4 | 0b10 << 6 | 0b01 << 8 # MOS6581, MOS8580, MOS6581
        music, errors = self._load(self._sidFile(version=3, flags=flags, secondSid=0x42)) # $42 is $d420
        self.assertEqual(errors, [])
        self.assertEqual((music.sidAddresses, music.sidModels), ([0xd400, 0xd420], ['MOS6581', 'MOS8580']))
        music, errors = self._load(self._sidFile(version=4, flags=flags, secondSid=0x42, thirdSid=0xe0))
        self.assertEqual((music.sidAddresses, music.sidModels), ([0xd400, 0xd420, 0xde00], ['MOS6581', 'MOS8580', 'MOS6581']))
        music, errors = self._load(self._sidFile(version=2, secondSid=0x42, thirdSid=0xe0)) # reserved before version 3 and 4
        self.assertEqual(music.sidAddresses, [0xd400])
        for address in [0x43, 0x40, 0x80, 0xd4, 0xff]: # odd, or outside $42-$7f and $e0-$fe
            with self.subTest(address=address):
                music, errors = self._load(self._sidFile(version=4, secondSid=address, thirdSid=address))
                self.assertEqual(music.sidAddresses, [0xd400])

    def testRsid(self):
        """RSID has versions 2 to 4, with the load address in the data, and no play address."""
        for version in [2, 3, 4]:
            with self.subTest(version=version):
                music, errors = self._load(self._sidFile(magicId=b'RSID', version=version, loadAddress=0, initAddress=0x1000, playAddress=0,
                                                         data=b'\x00\x10\x60'))
                self.assertEqual(errors, [])
                self.assertEqual((music.magicId, music.version), ('RSID', version))
                self.assertEqual((music.loadAddress, music.initAddress, music.playAddress, music.data), (0x1000, 0x1000, 0, b'\x60'))
        music, errors = self._load(self._sidFile(magicId=b'RSID', loadAddress=0, initAddress=0, playAddress=0, flags=0b10,
                                                 data=b'\x01\x08\x00')) # a BASIC program, started with RUN
        self.assertEqual(errors, [])
        self.assertEqual((music.isBasic, music.isPlaySidSpecific, music.initAddress), (True, False, 0))

    def testSpeed(self):
        """Bit n of the speed is set if song n+1 uses a CIA timer, with bit 31 for song 32 and later."""
        music, errors = self._load(self._sidFile(songs=40, speed=0b101 | 1 << 31))
        self.assertEqual([song for song in range(1, 41) if music.usesCiaTimer(song)], [1, 3] + list(range(32, 41)))

    def testInvalid(self):
        """Invalid files report an error, and return None."""
        for name, filename, error in [
            ('not found',          os.path.join(self.directory, 'missing.sid'),                             'File not found'),
            ('magic id',           self._sidFile(magicId=b'MSID'),                                          'Not a valid sid file'),
            ('short header',       self._sidFile(dataOffset=0x20, data=b''),                                'Not a valid sid file'),
            ('PSID version',       self._sidFile(version=5),                                                'unsupported PSID version 5'),
            ('RSID version 1',     self._sidFile(magicId=b'RSID', version=1, loadAddress=0, playAddress=0), 'unsupported RSID version 1'),
            ('data offset',        self._sidFile(version=2, dataOffset=0x76),                               'data offset'),
            ('no data',            self._sidFile(data=b''),                                                 'no music data'),
            ('no data after load', self._sidFile(loadAddress=0, data=b'\x00\x10'),                          'no music data'),
            ('past $ffff',         self._sidFile(loadAddress=0xfffe, data=b'\x60\x60\x60'),                 'past $ffff'),
            ('MUS data',           self._sidFile(flags=0b01),                                               'Sidplayer MUS'),
            ('RSID load',          self._sidFile(magicId=b'RSID', loadAddress=0x1000, playAddress=0),       'RSID load address'),
            ('RSID play',          self._sidFile(magicId=b'RSID', loadAddress=0, data=b'\x00\x10\x60'),     'RSID play address'),
            ('RSID speed',         self._sidFile(magicId=b'RSID', loadAddress=0, playAddress=0, speed=1,
                                                 data=b'\x00\x10\x60'),                                     'RSID speed')]:
            with self.subTest(name=name):
                music, errors = self._load(filename)
                self.assertIsNone(music)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(error, errors[0])


if __name__ == '__main__':
    unittest.main()
