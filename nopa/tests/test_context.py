#! /usr/bin/env python3
"""Tests of the assembler state."""

import unittest

from ..context import Context, NamespaceSymbols, dottedNames
from ..cpu import CPU_6502


class TestContext(unittest.TestCase):
    """Tests of the read pointer stack and the messages."""

    def testCPU(self):
        """A pass assembles for the 6502."""
        self.assertIs(Context({}).cpu, CPU_6502)

    def testReadPointerStack(self):
        """The read pointer stack, including the empty stack cases."""
        context = Context({})
        self.assertEqual(context.readPointer(), None)            # empty stack
        self.assertEqual(context.popReadPointer(), None)
        self.assertEqual(context.advanceReadPointer(), None)
        context.jumpReadPointer(('a.asm', 5))                    # no effect on an empty stack
        self.assertEqual(context.readPointer(), None)

        context.pushReadPointer(('a.asm', 0))
        self.assertEqual(context.advanceReadPointer(), ('a.asm', 1))
        context.pushReadPointer(('b.asm', 0))                    # e.g. an .import
        context.jumpReadPointer(('b.asm', 7))                    # e.g. .end jumping back
        self.assertEqual(context.readPointer(), ('b.asm', 7))
        self.assertEqual(context.popReadPointer(), ('b.asm', 7)) # end of b.asm
        self.assertEqual(context.readPointer(), ('a.asm', 1))    # back in a.asm

    def testDottedNames(self):
        """The dotted names in compiled code, as a name and its attributes, also after more than 255 other names."""
        manyNames = ''.join(f'v{i} = {i}\n' for i in range(300)) # Python then puts EXTENDED_ARG before the instructions
        for code, expected in [
            ('spr.util.draw',           [['spr', 'util', 'draw']]),
            ('spr.twice(4) + lo(x)',    [['spr', 'twice']]),       # a method call, and names without dots
            (manyNames + 'r = spr.draw', [['spr', 'draw']]),
        ]:
            with self.subTest(code=code[-20:]):
                self.assertEqual(dottedNames(compile(code, 'test', 'exec')), expected)

    def testDottedNamesCached(self):
        """The dotted names of an expression are found once, as it compiles to an equal code object in every pass."""
        first = dottedNames(compile('spr.draw', 'test', 'eval'))
        self.assertIs(dottedNames(compile('spr.draw', 'test', 'eval')), first)

    def testNamespaceCandidates(self):
        """A name in a namespace is looked up as its own, e.g. spr.util.draw, and then as it is if it is built in,
        but not in the namespace it is in. A name keeps its case, and _ is always the current address."""
        view = NamespaceSymbols({}, ('spr', 'util'), {'lo', '_'})
        for name, expected in [
            ('draw',  ['spr.util.draw']),
            ('SPEED', ['spr.util.SPEED']),
            ('lo',    ['spr.util.lo', 'lo']),
            ('_',     ['_', '_']),
        ]:
            with self.subTest(name=name):
                self.assertEqual(view.candidates(name), expected)
        self.assertEqual(NamespaceSymbols({}, ('spr',), set()).candidates('draw'), ['spr.draw'])

    def testNamespaceSymbols(self):
        """Code outside a namespace sees the symbols, and code in one a view of them, the same one during a pass."""
        context = Context({})
        self.assertIs(context.namespaceSymbols(), context.symbols)
        context.pushReadPointer(('a.asm', 0), 'spr')
        view = context.namespaceSymbols()
        self.assertIsInstance(view, NamespaceSymbols)
        self.assertEqual(view.candidates('draw'), ['spr.draw'])
        self.assertIs(context.namespaceSymbols(), view)

    def testZeroPage(self):
        """zp(size) allocates zero page bytes from $02, and returns the address of the first."""
        context = Context({})
        self.assertEqual([context.symbols['zp'](size) for size in [1, 2, 1, 8, 1]], [0x02, 0x03, 0x05, 0x06, 0x0e])

    def testReport(self):
        """Warnings and errors are prefixed with the file and line, if any."""
        context = Context({})
        context.reportWarning('no position')
        context.pushReadPointer(('a.asm', 4))                    # line index 4 is line 5
        context.reportWarning('careful')
        context.reportError('failed')
        self.assertEqual(context.warnings, ['warning: no position', 'a.asm:5: warning: careful'])
        self.assertEqual(context.errors, ['a.asm:5: error: failed'])


if __name__ == '__main__':
    unittest.main()
