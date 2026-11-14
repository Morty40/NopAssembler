#! /usr/bin/env python3
"""Tests of the assembler state."""

import unittest

from ..context import Context, NamespaceSymbols
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

    def testNamespaceCandidates(self):
        """A name in a namespace is looked up innermost first, then in the outer namespaces, then as it is.
        A constant keeps its capitals, and _ is always the current address."""
        view = NamespaceSymbols({}, ('spr', 'util'))
        for name, expected in [
            ('draw',  ['spr_util_draw', 'spr_draw', 'draw']),
            ('SPEED', ['SPR_UTIL_SPEED', 'SPR_SPEED', 'SPEED']),
            ('_',     ['_', '_', '_']),
        ]:
            with self.subTest(name=name):
                self.assertEqual(view.candidates(name), expected)
        self.assertEqual(NamespaceSymbols({}, ('spr',)).candidates('draw'), ['spr_draw', 'draw'])

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
