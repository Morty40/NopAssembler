#! /usr/bin/env python3
"""Tests of the expression evaluation."""

import unittest

from ..context import Context
from .. import text
from ..evaluate import byteExpression, byteValue, expression, intExpression, intValue, wordExpression, wordValue


class TestEvaluate(unittest.TestCase):
    """Tests of evaluating expressions."""

    def testEvalExpression(self):
        """Any Python expression, with the symbols as variables. A failure is an error, and gives None."""
        context = Context({})
        value = expression('123', context)
        self.assertEqual(value, 123)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({'abc': 234})
        value = expression('abc', context)
        self.assertEqual(value, 234)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = expression('abc', context)
        self.assertEqual(value, None)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 1)

    def testEvalIntExpression(self):
        """A float is truncated, with a warning. Infinity and NaN are not ints, so they are an error, and give 0."""
        context = Context({})
        value = intExpression('12', context)
        self.assertEqual(value, 12)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = intExpression('1.2', context)
        self.assertEqual(value, 1)
        self.assertEqual(len(context.warnings), 1)
        self.assertEqual(len(context.errors), 0)

        for e in ['inf', '-inf', 'nan']:
            with self.subTest(e=e):
                context = Context({})
                value = intExpression(e, context)
                self.assertEqual(value, 0)
                self.assertEqual(len(context.warnings), 0)
                self.assertEqual(context.errors, [f'error: Expected an int value instead of: "{e}"'])

    def testEvalByteExpression(self):
        """A negative byte is two's complement. Out of range is an error, and keeps the low byte."""
        context = Context({})
        value = byteExpression('-10', context)
        self.assertEqual(value, 0xf6)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = byteExpression('0x10', context)
        self.assertEqual(value, 0x10)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = byteExpression('0xfff', context)
        self.assertEqual(value, 0xff)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 1)

    def testEvalWordExpression(self):
        """A negative word is two's complement. Out of range is an error, and keeps the low word."""
        context = Context({})
        value = wordExpression('-10', context)
        self.assertEqual(value, 0xfff6)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = wordExpression('0x1000', context)
        self.assertEqual(value, 0x1000)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

        context = Context({})
        value = wordExpression('0xfffff', context)
        self.assertEqual(value, 0xffff)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 1)

    def testValues(self):
        """A value is checked as an expression's value is, and a message shows its repr."""
        for check, value, expected, warnings, errors in [
            (intValue,  2,       2,      [],                                       []),
            (intValue,  2.5,     2,      ['warning: Truncating float value: 2.5'], []),
            (intValue,  'B',     0,      [],                                       ['error: Expected an int value instead of: "\'B\'"']),
            (byteValue, -10,     0xf6,   [],                                       []),
            (byteValue, 0x123,   0x23,   [],                                       ['error: Byte value out of range: 291']),
            (wordValue, -10,     0xfff6, [],                                       []),
            (wordValue, 0x12345, 0x2345, [],                                       ['error: Word value out of range: 74565']),
        ]:
            with self.subTest(check=check.__name__, value=value):
                context = Context({})
                self.assertEqual(check(value, context), expected)
                self.assertEqual(context.warnings, warnings)
                self.assertEqual(context.errors, errors)

    def testEncodingFunctions(self):
        """ord() and chr() in expressions use the current encoding."""
        context = Context({})
        self.assertEqual(expression('ord("A")', context), 1)
        self.assertEqual(expression('chr(1)', context), 'A')
        context.encoding = text.ENCODING_PETSCII_UPPER
        self.assertEqual(expression('ord("A")', context), 65)
        self.assertEqual(expression('chr(65)', context), 'A')
        self.assertEqual(len(context.errors), 0)

    def testDivZeroExpression(self):
        """Dividing by zero is an error, and gives None."""
        context = Context({})
        value = expression('0/0', context)
        self.assertEqual(value, None)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 1)


if __name__ == '__main__':
    unittest.main()
