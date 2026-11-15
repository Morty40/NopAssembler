#! /usr/bin/env python3
"""Evaluation of Python expressions, with the assembler symbols as variables."""

import builtins
import math

from .context import Context


def expression(e: str, context: Context):
    """Evaluate a Python expression, or report an error and return None."""
    value = None
    try:
        code = compile(e, '<string>', 'eval')
        context.noteReferences(code)
        value = builtins.eval(code, context.namespaceSymbols())
    except Exception as exception:
        message = str(exception) # capitalize only the first letter, keeping the case of names
        context.reportError(f'{message[:1].upper()}{message[1:]}: "{e}"')
    return value


def intValue(value, e: str, context: Context) -> int:
    """Check a value of the expression e as an int. Floats are truncated, other types give an error,
    as do infinity and NaN, which have no int."""
    if type(value) is float and math.isfinite(value):
        truncated = int(value)
        if value != float(truncated):
            context.reportWarning(f'Truncating float value: {value}')
        value = truncated
    if type(value) is not int:
        context.reportError(f'Expected an int value instead of: "{e}"')
        value = 0
    return value


def byteValue(value, e: str, context: Context) -> int:
    """Check a value of the expression e as a byte from -128 to 255, negative in two's complement."""
    value = intValue(value, e, context)
    if value < -128 or value > 255:
        context.reportError(f'Byte value out of range: {value}')
    return value & 0xff


def wordValue(value, e: str, context: Context) -> int:
    """Check a value of the expression e as a word from -32768 to 65535, negative in two's complement."""
    value = intValue(value, e, context)
    if value < -32768 or value > 65535:
        context.reportError(f'Word value out of range: {value}')
    return value & 0xffff


def intExpression(e: str, context: Context) -> int:
    """Evaluate an int. Floats are truncated, other types give an error."""
    return intValue(expression(e, context), e, context)


def byteExpression(e: str, context: Context) -> int:
    """Evaluate a byte from -128 to 255, negative in two's complement."""
    return byteValue(expression(e, context), e, context)


def wordExpression(e: str, context: Context) -> int:
    """Evaluate a word from -32768 to 65535, negative in two's complement."""
    return wordValue(expression(e, context), e, context)
