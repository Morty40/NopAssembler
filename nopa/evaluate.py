#! /usr/bin/env python3
"""Evaluation of Python expressions, with the assembler symbols as variables."""

import builtins
import types

from .context import Context


def expression(e: str, context: Context):
    """Evaluate a Python expression, or report an error and return None."""
    value = None
    try:
        code = compile(e, '<string>', 'eval')
        context.noteReferences(code)
        value = builtins.eval(code, context.symbols)
    except Exception as exception:
        message = str(exception) # capitalize only the first letter, keeping the case of names
        context.reportError(f'{message[:1].upper()}{message[1:]}: "{e}"')
    return value


def intExpression(e: str, context: Context) -> int:
    """Evaluate an int. Floats are truncated, other types give an error."""
    value = expression(e, context)
    if type(value) is float:
        intValue = int(value)
        if value != float(intValue):
            context.reportWarning(f'Truncating float value: {value}')
        value = intValue
    if type(value) is not int:
        context.reportError(f'Expected an int value instead of: "{e}"')
        value = 0
    return value


def byteExpression(e: str, context: Context) -> int:
    """Evaluate a byte from -128 to 255, negative in two's complement."""
    value = intExpression(e, context)
    if value < -128 or value > 255:
        context.reportError(f'Byte value out of range: {value}')
    return value & 0xff


def wordExpression(e: str, context: Context) -> int:
    """Evaluate a word from -32768 to 65535, negative in two's complement."""
    value = intExpression(e, context)
    if value < -32768 or value > 65535:
        context.reportError(f'Word value out of range: {value}')
    return value & 0xffff


def lambdaExpression(e: str, context: Context):
    """Evaluate a lambda written without the keyword, e.g. "x: x * 2"."""
    value = expression(f'lambda {e}', context)
    if not isinstance(value, types.FunctionType):
        context.reportError(f'Expected a function instead of: "{e}"')
        value = lambda x: x
    return value
