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

    def testEvalValueExpressions(self):
        """An int, byte or word expression is evaluated, and its value checked as by intValue, byteValue and wordValue,
        with the expression in the message."""
        for check, e, expected, errors in [
            (intExpression,  '1 + 1',         2,      []),
            (byteExpression, '-10',           0xf6,   []),
            (wordExpression, '0x10000 - 1',   0xffff, []),
            (intExpression,  'str(5)',        0,      ['error: Expected an int value instead of: "str(5)"']), # not the value, '5'
        ]:
            with self.subTest(e=e):
                context = Context({})
                self.assertEqual(check(e, context), expected)
                self.assertEqual(context.warnings, [])
                self.assertEqual(context.errors, errors)

    def testValues(self):
        """A value is checked as an int, byte or word: a float is truncated, with a warning, while infinity and NaN,
        which have no int, are errors, as other types are. A message shows the value's repr."""
        for check, value, expected, warnings, errors in [
            (intValue,  2,             2,      [],                                       []),
            (intValue,  2.5,           2,      ['warning: Truncating float value: 2.5'], []),
            (intValue,  'B',           0,      [],                                       ['error: Expected an int value instead of: "\'B\'"']),
            (intValue,  float('inf'),  0,      [],                                       ['error: Expected an int value instead of: "inf"']),
            (intValue,  float('-inf'), 0,      [],                                       ['error: Expected an int value instead of: "-inf"']),
            (intValue,  float('nan'),  0,      [],                                       ['error: Expected an int value instead of: "nan"']),
            (byteValue, -10,           0xf6,   [],                                       []),
            (byteValue, 0x123,         0x23,   [],                                       ['error: Byte value out of range: 291']),
            (wordValue, -10,           0xfff6, [],                                       []),
            (wordValue, 0x12345,       0x2345, [],                                       ['error: Word value out of range: 74565']),
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
