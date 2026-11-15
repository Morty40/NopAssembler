#! /usr/bin/env python3
"""Evaluation of Python expressions, with the assembler symbols as variables."""

import builtins
import math

from .context import Context


def exceptionMessage(exception: Exception) -> str:
    """The text of an exception for an error, with only the first letter capitalized, keeping the case of names.
    The type goes first when the text alone doesn't say what failed: when there is none, e.g. a failed assert,
    or it is only the key, e.g. KeyError: 1."""
    message = str(exception)
    if not message:
        message = type(exception).__name__
    elif isinstance(exception, KeyError):
        message = f'{type(exception).__name__}: {message}'
    return f'{message[:1].upper()}{message[1:]}'


def expression(e: str, context: Context):
    """Evaluate a Python expression, or report an error and return None."""
    value = None
    try:
        code = compile(e, '<string>', 'eval')
        context.noteReferences(code)
        value = builtins.eval(code, context.namespaceSymbols())
    except Exception as exception:
        context.reportError(f'{exceptionMessage(exception)}: "{e}"')
    return value


def intValue(value, context: Context, e: str | None = None) -> int:
    """Check a value as an int. Floats are truncated, other types give an error, as do infinity and NaN,
    which have no int. The message shows the expression e, or else the value's repr."""
    if type(value) is float and math.isfinite(value):
        truncated = int(value)
        if value != float(truncated):
            context.reportWarning(f'Truncating float value: {value}')
        value = truncated
    if type(value) is not int:
        context.reportError(f'Expected an int value instead of: "{e if e is not None else repr(value)}"')
        value = 0
    return value


def byteValue(value, context: Context, e: str | None = None) -> int:
    """Check a value as a byte from -128 to 255, negative in two's complement."""
    value = intValue(value, context, e)
    if value < -128 or value > 255:
        context.reportError(f'Byte value out of range: {value}')
    return value & 0xff


def wordValue(value, context: Context, e: str | None = None) -> int:
    """Check a value as a word from -32768 to 65535, negative in two's complement."""
    value = intValue(value, context, e)
    if value < -32768 or value > 65535:
        context.reportError(f'Word value out of range: {value}')
    return value & 0xffff


def intExpression(e: str, context: Context) -> int:
    """Evaluate an int. Floats are truncated, other types give an error."""
    return intValue(expression(e, context), context, e)


def byteExpression(e: str, context: Context) -> int:
    """Evaluate a byte from -128 to 255, negative in two's complement."""
    return byteValue(expression(e, context), context, e)


def wordExpression(e: str, context: Context) -> int:
    """Evaluate a word from -32768 to 65535, negative in two's complement."""
    return wordValue(expression(e, context), context, e)
