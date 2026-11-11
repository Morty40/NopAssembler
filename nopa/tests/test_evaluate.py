#! /usr/bin/env python3
"""Tests of the expression evaluation."""

import unittest
import types

from ..context import Context
from .. import text
from ..evaluate import byteExpression, expression, intExpression, lambdaExpression, wordExpression


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
        """A float is truncated, with a warning."""
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

    def testEvalLambdaExpression(self):
        """The text after "lambda" becomes a function, with the symbols and the math functions available."""
        context = Context({'k': 1})
        value = lambdaExpression('x: x + k + round(cos(0))', context)
        self.assertEqual(isinstance(value, types.FunctionType), True)
        self.assertEqual(value(1), 3)
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 0)

    def testEvalLambdaExpressionError(self):
        """Text that isn't a function is an error, and gives the identity function."""
        context = Context({})
        value = lambdaExpression('1', context) # not a lambda: "lambda 1" is invalid syntax
        self.assertEqual(isinstance(value, types.FunctionType), True)
        self.assertEqual(value(5), 5) # falls back to the identity function
        self.assertEqual(len(context.warnings), 0)
        self.assertEqual(len(context.errors), 2) # the syntax error, and the expected function
        self.assertEqual(context.errors[-1], 'error: Expected a function instead of: "1"')

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
