#! /usr/bin/env python3
"""Tests of the directives."""

import os
import tempfile
import unittest

from .. import lexer
from ..assemble import assembleFile
from ..context import Context
from ..directives import assemble, byte, bytefill, _matches, org, printValues


class TestDirectives(unittest.TestCase):
    """Tests of the directive arguments, and what the directives store."""

    def _assemble(self, source: str, files: dict | None = None) -> tuple[dict, list]:
        """Assemble source, with the files {name: text or bytes} beside it, and return the memory, and the errors without the folder."""
        with tempfile.TemporaryDirectory() as directory:
            for name, content in {'test.asm': source, **(files or {})}.items():
                with open(os.path.join(directory, name), 'wb' if type(content) is bytes else 'w') as f:
                    f.write(content)
            context = assembleFile(os.path.join(directory, 'test.asm'))
            return context.memory, [error.replace(directory + os.sep, '') for error in context.errors]

    def _memory(self, source: str, files: dict | None = None) -> dict:
        """Assemble source without errors, with the files {name: text} beside it, and return the memory."""
        memory, errors = self._assemble(source, files)
        self.assertEqual(errors, [])
        return memory

    def _errors(self, source: str, files: dict | None = None) -> list:
        """Assemble source, with the files {name: text} beside it, and return the errors, without the folder."""
        memory, errors = self._assemble(source, files)
        return errors

    def _assertBytes(self, source: str, expected: list, files: dict | None = None):
        """Source stores exactly the expected bytes, without gaps, from the default address $1000."""
        memory = self._memory(source, files)
        self.assertEqual([memory.get(0x1000 + i) for i in range(len(expected))], expected)
        self.assertEqual(len(memory), len(expected))

    def testMatches(self):
        """Arguments are checked against the parameters, and their type annotations."""
        self.assertTrue(_matches(org, [0x1000]))
        self.assertFalse(_matches(org, []))                  # missing argument
        self.assertFalse(_matches(org, [1, 2]))              # too many arguments
        self.assertFalse(_matches(org, ['a']))               # wrong type
        self.assertFalse(_matches(org, [True]))              # a bool is not an int
        self.assertTrue(_matches(bytefill, [3]))             # optional argument
        self.assertTrue(_matches(bytefill, [3, 'x: x']))
        self.assertTrue(_matches(bytefill, [3, None]))       # one of the types in an optional argument
        self.assertFalse(_matches(bytefill, [3, 5]))         # none of them
        self.assertTrue(_matches(byte, []))                  # any number of any type
        self.assertTrue(_matches(byte, [1, 'a', 2.5]))
        self.assertFalse(_matches(printValues, []))          # at least one

    def testBitsWithInt(self):
        """.bits needs a string with the bit pattern."""
        context = Context({})
        assemble(lexer.tokenize('.bits 3')[:-1], context)
        self.assertEqual(context.errors, ['error: Invalid directive: .bits 3'])

    def testStoredBytes(self):
        """The directives that store bytes, including values given after they are used."""
        for source, expected in [
            ('.byte -128, 0, 127, 255',                  [0x80, 0x00, 0x7f, 0xff]), # no newline at the end
            ('.word -32768, 0, 32767, 65535',            [0x00, 0x80, 0x00, 0x00, 0xff, 0x7f, 0xff, 0xff]),
            ('.bits "00000000"\n',                       [0]),
            ('.bits "000000010000001000000011"\n',       [1, 2, 3]),
            ('.bits "     #  "\n',                       [4]), # # is a 1 bit, and a space a 0 bit
            ('.bits "     # #     ##      ###"\n',       [5, 6, 7]),
            ('.encoding ENCODING_SCREEN_UPPER\n.string "ABC", "DEF"\n', [1, 2, 3, 0, 4, 5, 6, 0]),
            ('.bytefill 3\n',                            [0, 0, 0]),
            ('.bytefill 3, "x: x+N"\nN = 1\n',           [1, 2, 3]), # x is the index, and N is assigned later
            ('.wordfill 3\n',                            [0, 0, 0, 0, 0, 0]),
            ('.wordfill 3, "x: x+N"\nN = 1\n',           [1, 0, 2, 0, 3, 0]),
            ('lda aa\nlda bb\naa = zp(1)\nbb = zp(1)\n', [0xa5, 0x02, 0xa5, 0x03]), # zero page lda, though used before zp()
            ('lda aa\nlda bb\naa = zp(2)\nbb = zp(2)\n', [0xa5, 0x02, 0xa5, 0x04]), # two bytes each
            ('buffer = zp(8)\nnext = zp(1)\nlda next\n', [0xa5, 0x0a]),             # buffer is $02 to $09
        ]:
            with self.subTest(source=source):
                self._assertBytes(source, expected)

    def testAddresses(self):
        """.org, .align and assigning _ choose the address of the next byte."""
        for source, expected in [
            ('.org $1000\n.align 16\n.byte 1\n.align 16\n.byte 2\n', {0x1000: 1, 0x1010: 2}), # $1000 is already aligned
            ('.org $2000\n.byte 1\n_ = $2010\n.byte 2\n',            {0x2000: 1, 0x2010: 2}),
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._memory(source), expected)

    def testCPU(self):
        """.cpu chooses the instructions from the next line on, the 6502 by default."""
        for source, expected in [
            ('lax $10\n',                                       [0xa7, 0x10]),                    # the 6502 by default
            ('.cpu CPU_65C02\nstz $d020\nlda ($12)\n',          [0x9c, 0x20, 0xd0, 0xb2, 0x12]),
            ('.cpu CPU_65C02\nbra later\n.cpu CPU_6502\nlater: lax $10\n', [0x80, 0x00, 0xa7, 0x10]),  # switching, bra to the next line is offset 0
            ('.cpu CPU_R65C02\nloop: rmb3 $12\nbbr3 $12,loop\n',  [0x37, 0x12, 0x3f, 0x12, 0xfb]), # back to loop is offset -5
            ('.cpu CPU_W65C02\nwai\nstp\nsmb0 $12\n',             [0xcb, 0xdb, 0x87, 0x12]),
        ]:
            with self.subTest(source=source):
                self._assertBytes(source, expected)

    def testImport(self):
        """.import assembles a source file, or runs a Python file, found beside the main source file."""
        self._assertBytes('.import "bytes.txt"\n', [1, 2, 3], {'bytes.txt': '.byte 1, 2, 3\n'})
        self._assertBytes('.import "fill.py"\n@fill(4, 2)\n', [4, 4], {'fill.py': 'def fill(x, n):\n    return f".byte {x}\\n" * n\n'})

    def testImportNamespace(self):
        """A .py file imported into a namespace runs in a module of that name, so its names are used as namespace.name."""
        files = {'util.py': 'x = 5\ndef double(v):\n    return v * 2\n'}
        for source, expected in [
            ('.import "util.py", "util"\n.byte util.x\n',         [5]),
            ('.import "util.py", "util"\n.byte util.double(3)\n', [6]),
            ('.import "util.py", "UTIL"\n.byte UTIL.x\n',         [5]),
            ('.byte util.x\n.import "util.py", "util"\n',         [5]),  # used before the import, with util from the last pass
        ]:
            with self.subTest(source=source):
                self._assertBytes(source, expected, files)

    def testImportNamespaceGenerators(self):
        """A generator in a namespace is called as @namespace.name(), and its local labels are named after the name,
        also when two namespaces have a generator of the same name. Its code is assembled with the global names."""
        wait = 'def wait():\n    return "_x: dex\\nbne _x\\n"\n'
        files = {'a.py': wait, 'b.py': wait,
                 'util.py': 'COUNT = 2\ndef fill(v):\n    return f".byte {v}\\n" * COUNT\ndef jump():\n    return "jmp end\\n"\n'}
        for source, expected in [
            ('.import "a.py", "a"\n@a.wait()\n',                                     [0xca, 0xd0, 0xfd]),       # dex, bne -3 to wait1_x
            ('.import "a.py", "a"\n.import "b.py", "b"\n@a.wait()\n@b.wait()\n',     [0xca, 0xd0, 0xfd, 0xca, 0xd0, 0xfd]), # wait1_x and wait2_x
            ('.import "util.py", "util"\nv = 7\n@util.fill(v)\n',                    [7, 7]),                   # COUNT from its module
            ('.import "util.py", "util"\n@util.jump()\nend: rts\n',                  [0x4c, 0x03, 0x10, 0x60]), # jmp to the global label end, at $1003
        ]:
            with self.subTest(source=source):
                self._assertBytes(source, expected, files)

    def testImportPythonSyntaxError(self):
        """A syntax error in an imported Python file is reported with the file's name and line, also in a namespace."""
        files = {'bad.py': 'x = 1\ny = (\n'}
        for source in ['.import "bad.py"\n', '.import "bad.py", "bad"\n']:
            with self.subTest(source=source):
                errors = self._errors(source, files)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn("(SyntaxError: '(' was never closed (bad.py, line 2))", errors[0])

    def testImportNamespaceNotAssembled(self):
        """A namespace imported in a block that is not assembled is not defined, like other symbols."""
        source = '.if ref("t")\nt: nop\n.import "util.py", "util"\n.end\n.byte util.x\n' # nothing uses t, so the block is never assembled
        self.assertEqual(self._errors(source, {'util.py': 'x = 5\n'}), ['test.asm:5: error: Name \'util\' is not defined: "util.x"'])

    def testImportNamespaceIsolated(self):
        """The names of a file in a namespace are not global, and the file doesn't see the global names."""
        files = {'util.py': 'x = 5\n', 'low.py': 'y = lo(1)\n'} # lo() is a global symbol, not a Python built-in
        for source, expected in [
            ('.import "util.py", "util"\n.byte x\n', ['test.asm:2: error: Name \'x\' is not defined: "x"']),
            ('.import "low.py", "low"\n',            ['test.asm:1: error: Failed to execute python code: "low.py" '
                                                      "(NameError: name 'lo' is not defined)"]),
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._errors(source, files), expected)

    def testImportNamespaceMerged(self):
        """Files imported into the same namespace share it, and a later file sees the names of an earlier one."""
        files = {'a.py': 'x = 1\n', 'b.py': 'y = x + 1\n'}
        for source, expected in [
            ('.import "a.py", "util"\n.import "b.py", "util"\n.byte util.x, util.y\n', [1, 2]),
            ('.import "a.py", "util"\n.import "a.py", "util"\n.byte util.x\n',         [1]),     # the same file twice
            ('.byte util.y\n.import "a.py", "util"\n.import "b.py", "util"\n',         [2]),     # used before the imports, from the last pass
        ]:
            with self.subTest(source=source):
                self._assertBytes(source, expected, files)

    def testImportNamespaceTaken(self):
        """A namespace can't be the name of another symbol, such as a label or a module imported by Python code,
        or of a Python built-in, and the file isn't run then."""
        files = {'bad.py': '1/0\n'} # fails if it runs, so a second error would show that it ran
        for source, expected in [
            ('.import "bad.py", "sin"\n',                           ['test.asm:1: error: Symbol "sin" cannot change type from builtin_function_or_method to Namespace']),
            ('util: nop\n.import "bad.py", "util"\n',               ['test.asm:2: error: Symbol "util" cannot change type from int to Namespace']),
            ('.python\nimport os\n.end\n.import "bad.py", "os"\n', ['test.asm:4: error: Symbol "os" cannot change type from module to Namespace']),
            ('.import "bad.py", "len"\n',                           ['test.asm:1: error: Namespace must be a name that isn\'t a Python keyword or built-in, and doesn\'t start with _: "len"']),
            ('.import "bad.py", "print"\n',                         ['test.asm:1: error: Namespace must be a name that isn\'t a Python keyword or built-in, and doesn\'t start with _: "print"']),
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._errors(source, files), expected)

    def testImportNamespaceMessages(self):
        """Only a .py file can be imported into a namespace, and the namespace is a name that isn't a Python keyword
        or built-in, and doesn't start with _."""
        files = {'util.py': 'x = 1\n', 'bytes.txt': '.byte 1\n'}
        for source, expected in [
            ('.import "util.py", "util"\n',    []),
            ('.import "util.py", "myUtil"\n',  []),
            ('.import "util.py", "my_util"\n', []),
            ('.import "util.py", "Util2"\n',   []),
            ('.import "util.py", "UTIL"\n',    []),
            ('.import "bytes.txt", "util"\n',  ['test.asm:1: error: Only a .py file can be imported into a namespace: "bytes.txt"']),
            ('.import "util.py", "my-util"\n', ['test.asm:1: error: Namespace must be a name that isn\'t a Python keyword or built-in, and doesn\'t start with _: "my-util"']),
            ('.import "util.py", "if"\n',      ['test.asm:1: error: Namespace must be a name that isn\'t a Python keyword or built-in, and doesn\'t start with _: "if"']),
            ('.import "util.py", "_util"\n',   ['test.asm:1: error: Namespace must be a name that isn\'t a Python keyword or built-in, and doesn\'t start with _: "_util"']),
        ]:
            with self.subTest(source=source):
                self.assertEqual(self._errors(source, files), expected)

    def testImportPythonReferences(self):
        """The names used by an imported Python file count as references, also inside its functions."""
        # g is never called, but its use of f is enough to assemble the optional block
        self._assertBytes('.import "uses.py"\n.optional\nf: nop\n.end\n', [0xea], {'uses.py': 'def g():\n    return f\n'})

    def testImportNamespaceReferences(self):
        """The names used by a Python file in a namespace are its own, so they don't count as references,
        but the code its generators return does."""
        files = {'lib.py': 'def init():\n    return ""\ndef call():\n    return "jsr init\\n"\n'}
        for source, expected in [
            ('.import "lib.py", "lib"\n.optional\ninit: rts\n.end\n.byte 0\n',     [0]),                      # init isn't used
            ('.import "lib.py", "lib"\n@lib.call()\n.optional\ninit: rts\n.end\n', [0x20, 0x03, 0x10, 0x60]), # jsr init, at $1003, so the block is assembled
        ]:
            with self.subTest(source=source):
                self._assertBytes(source, expected, files)

    def testImportPythonMessages(self):
        """A Python file that fails is reported by its name, whatever goes wrong."""
        for content, exception in [
            (b'x = (\n',  'SyntaxError'),
            (b'1/0\n',    'ZeroDivisionError'),
            (b'\xff\xfe', 'UnicodeDecodeError'), # can't be read
        ]:
            with self.subTest(exception=exception):
                errors = self._errors('.import "bad.py"\n', {'bad.py': content})
                self.assertEqual(len(errors), 1, errors)
                self.assertIn(f'test.asm:1: error: Failed to execute python code: "bad.py" ({exception}', errors[0])

    def testIf(self):
        """.if blocks, with .else and .end."""
        for source, expected in [
            ('.if a>5\n.byte 1\n.end\n',                       [1]),   # true
            ('.if a<5\n.byte $ee\n.end\n',                     []),    # false, so the lines are skipped
            ('.if a>5\n.byte 2\n.else\n.byte $ee\n.end\n',     [2]),   # true, with else
            ('.if a<5\n.byte $ee\n.else\n.byte 3\n.end\n',     [3]),   # false, with else
            ('.if a>5\n.if a<5\n.byte $ee\n.else\n.byte 4\n.end\n.end\n', [4]), # nested
            ('.if a<5\ninner: .if a>5\n.byte $ee\n.else\n.byte $ee\n.end\n'     # skipped, with a label, a nested if and a loop
             '.repeat 2\n.byte $ee\n.end\n.else\n.byte 5\n.end\n', [5]),
            ('.if a>5\nboth: .byte 6\n.else\nboth: .byte $ee\n.end\n', [6]),    # the same label in both branches, as only one is assembled
            ('.if a>5 and not a>10\n.byte 7\n.end\n',          [7]),   # Python keywords in the condition
            ('.for i=0, i<4, i+=1\n.if i % 2 == 0\n.byte i\n.end\n.end\n', [0, 2]), # inside a loop
        ]:
            with self.subTest(source=source):
                self._assertBytes(f'a = 7\n{source}', expected) # a is 7 in every condition

    def testFor(self):
        """.for loops, with an initial statement, a condition and a step."""
        for source, expected in [
            ('.for a=0, a<4, a+=1\n.byte a\n.end\n',           [0, 1, 2, 3]),
            ('.for a=10, a<10, a+=1\n.byte $ee\n.end\n',       []),    # false at the start, so the loop is skipped
            ('.for a=0, a<0, a+=1\nskipped: .for b=0, b<2, b+=1\n.byte $ee\n.end\n.end\n', []), # with a label and a nested loop
            ('.for a=3, a>0, a-=1\n.byte a\n.end\n',           [3, 2, 1]), # counting down
            ('.for row=0, row<2, row+=1\n.for column=0, column<3, column+=1\n.byte row*16 + column\n.end\n.end\n',
             [0x00, 0x01, 0x02, 0x10, 0x11, 0x12]),                    # nested loops
            ('.for a=1, a<100, a*=2\n.byte a\n.end\n',         [1, 2, 4, 8, 16, 32, 64]), # any Python statement as the step
            ('.for i=0, i<len([5, 6]), i+=1\n.byte i\n.end\n', [0, 1]), # commas inside brackets
        ]:
            with self.subTest(source=source):
                self._assertBytes(source, expected)

    def testRepeat(self):
        """.repeat blocks, with the count as an expression."""
        for source, expected in [
            ('.repeat 3\n.byte $ee\n.end\n',                   [0xee, 0xee, 0xee]),
            ('.repeat 0\n.byte $ff\n.end\n',                   []),    # zero times, so the block is skipped
            ('.repeat 0\nskipped: .repeat 2\n.byte $ff\n.end\n.end\n', []), # with a label and a nested block
            ('.repeat 2\n.byte 1\n.repeat 2\n.byte 2\n.end\n.end\n', [1, 2, 2, 1, 2, 2]), # nested blocks
            ('.repeat 4 // 2\n.byte 3\n.end\n',                [3, 3]), # the count is an expression
            ('.repeat 2\n.for a=0, a<2, a+=1\n.byte a\n.end\n.end\n', [0, 1, 0, 1]), # a for loop inside
            ('.repeat 0\n.for a=0, a<2, a+=1\n.byte $ff\n.end\n.end\n', []), # skipped, with a for loop inside
        ]:
            with self.subTest(source=source):
                self._assertBytes(source, expected)

    def testPython(self):
        """.python blocks, from .python to .end."""
        for source, expected in [
            # the code at the same indentation as .python
            ('    .python\n    f = lambda x: x+2\n    .end\n.byte f(1)\n', [3]),
            # the code indented like the assembly around it, and lines after the block are assembled as before
            ("""
            .python
                def double(x):                       # indented like the assembly around it
                    return x * 2
                values = [1, 2]; total = sum(values) # ; separates Python statements, it is not a comment
                text = "$%"                          # $ and % are not changed into 0x and 0b
            .end
            .byte double(21)
            .byte total, len(text)
            .byte 7 % 4
            """, [0x2a, 3, 2, 3]),
            # a generator defined in a block
            ('.python\n    def nops(n):\n        return "nop\\n" * n\n.end\n@nops(2)\n', [0xea, 0xea]),
            # a block in skipped lines is skipped too
            ('.if 0\n.python\n    this is not valid Python, but it is skipped\n.end\n.end\n', []),
        ]:
            with self.subTest(source=source):
                self._assertBytes(source, expected)


if __name__ == '__main__':
    unittest.main()
