#! /usr/bin/env python3
"""The directives, such as .byte or .org, each a function in the DIRECTIVES table.

A directive's parameters declare the arguments it accepts, and their type
annotations the types, e.g. def org(context, address: int). Parameters
without an annotation accept any type, and Callable accepts any callable.
"""

import ast
import inspect
import itertools
import os
import typing
from collections.abc import Callable

from . import evaluate
from . import lexer
from . import text
from .context import Context, Namespace
from .cpu import CPU


DIRECTIVES: dict[str, Callable[..., object]] = {} # directive name: function
_rawDirectives: set[str] = set() # directives that get their arguments as tokens, e.g. .for i in range(8)


def directive(name: str, raw: bool = False):
    """Register a function as the directive with the given name.

    A raw directive gets its arguments as tokens, and the tokenized files.
    """
    def register(function):
        """Add the function to the directives table."""
        DIRECTIVES[name] = function
        if raw:
            _rawDirectives.add(name)
        return function
    return register


def _matches(function, arguments: list) -> bool:
    """Check that the arguments fit the function's parameters, and their type annotations."""
    parameters = inspect.signature(function).parameters
    try:
        bound = inspect.signature(function).bind(None, *arguments) # None for the context
    except TypeError:
        return False
    for name, value in list(bound.arguments.items())[1:]:
        expected = parameters[name].annotation
        values = value if parameters[name].kind == inspect.Parameter.VAR_POSITIONAL else [value]
        allowed = typing.get_args(expected) or (expected,) # the types of a union, e.g. str | None
        if expected is not inspect.Parameter.empty and not all(_fits(v, allowed) for v in values):
            return False
    return True


def _fits(value, allowed: tuple) -> bool:
    """A value is of one of the allowed types: exactly, so a bool is not an int, or any callable for Callable."""
    return type(value) in allowed or (Callable in allowed and callable(value))


def assemble(tokens: list, context: Context, chunks: dict | None = None) -> bool:
    """Assemble a directive line, e.g. .byte 1, 2.

    The arguments are evaluated as one expression, a tuple if several.
    chunks are the tokenized files, for directives that look ahead (.for).
    Returns False if the directive moved the read pointer (.import).
    """
    name = tokens[1].string
    if name in _rawDirectives:
        return DIRECTIVES[name](context, tokens[2:], chunks) is not False
    expression = lexer.join(tokens[2:])

    if not expression.strip():
        arguments = []
    else:
        value = evaluate.expression(expression, context)
        arguments = [] if value is None else list(value) if type(value) is tuple else [value]

    function = DIRECTIVES.get(name)
    if function is None or not _matches(function, arguments):
        context.reportError(f'Invalid directive: .{name} {expression}')
        return True
    return function(context, *arguments) is not False


@directive('byte')
def byte(context, *values):
    """Store bytes."""
    for value in values:
        context.store(evaluate.byteValue(value, context))


@directive('word')
def word(context, *values):
    """Store 16-bit words, low byte first."""
    for value in values:
        context.storeWord(evaluate.wordValue(value, context))


@directive('text')
def storeText(context, *texts: str):
    """Store texts, in the current text encoding."""
    _storeTexts(context, texts, zeroTerminated=False)


@directive('string')
def storeString(context, *texts: str):
    """Store texts, each followed by a zero byte."""
    _storeTexts(context, texts, zeroTerminated=True)


def _storeTexts(context, texts, zeroTerminated: bool):
    """Store texts in the current encoding, each optionally followed by a zero byte."""
    for t in texts:
        for char in t:
            o = text.ord(char, context.encoding)
            if o is not None:
                context.store(evaluate.byteValue(o, context)) # your own encoding can have any value
            else:
                context.reportError(f'Unknown character "{char}" in text "{t}"')
        if zeroTerminated:
            context.store(0)


@directive('encoding')
def encoding(context, encoding: dict):
    """Set the text encoding: a table of characters and their values."""
    context.encoding = encoding


@directive('cpu')
def setCPU(context, cpu: CPU):
    """Choose the cpu, and so the instructions, from the next line on, e.g. .cpu CPU_65C02."""
    context.cpu = cpu


@directive('bits')
def bits(context, pattern: str):
    """Store a bit pattern, 8 bits per byte, written with 0 and 1, or with space and # for 0 and 1."""
    characters = set(pattern)
    if not pattern:
        context.reportError('Bit pattern must not be empty')
    elif characters - set('01 #'):
        context.reportError(f'Bit pattern can only have 0, 1, space and #: "{pattern}"')
    elif characters & set('01') and characters & set(' #'):
        context.reportError(f'Bit pattern must have either 0 and 1, or space and #, not both: "{pattern}"')
    elif len(pattern) % 8 != 0:
        context.reportError(f'Bit pattern must have a multiple of 8 bits, not {len(pattern)}: "{pattern}"')
    else:
        pattern = pattern.replace(' ', '0').replace('#', '1')
        for i in range(0, len(pattern), 8):
            context.store(int(pattern[i:i + 8], 2))


@directive('bytefill')
def bytefill(context, n: int, function: Callable | None = None):
    """Store n bytes: zero, or the values of a function of the index, e.g. lambda x: x * 2."""
    _fill(context, n, function, context.store, evaluate.byteValue)


@directive('wordfill')
def wordfill(context, n: int, function: Callable | None = None):
    """Store n words: zero, or the values of a function of the index, e.g. lambda x: x * 2."""
    _fill(context, n, function, context.storeWord, evaluate.wordValue)


def _fill(context, n: int, function: Callable | None, store, checkValue):
    """Store n values, using the store function, each checked by checkValue. A value the function fails
    for is an error, with the index, and zero, so the size stays the same."""
    if n < 0:
        context.reportError(f'Count must not be negative: {n}')
        n = 0 # nothing stored
    f = function if function is not None else lambda x: 0
    for x in range(0, n):
        try:
            value = f(x)
        except Exception as exception:
            context.reportError(f'{evaluate.exceptionMessage(exception)}, at index {x}')
            value = 0
        store(checkValue(value, context))


@directive('org')
def org(context, address: int):
    """Set the current address."""
    context.symbols['_'] = address


@directive('section')
def section(context, name: str, address: int | None = None):
    """Switch to the named section: a new one starts at the address, an existing one continues where it stopped."""
    if name in context.sections and address is not None:
        context.reportError(f'Section already has an address: "{name}"')
    elif name not in context.sections and address is None:
        context.reportError(f'New section needs an address: "{name}"')
    if context.currentSection is not None:
        context.sections[context.currentSection] = context.symbols['_']
    context.currentSection = name
    context.symbols['_'] = context.sections.setdefault(name, address or 0)


@directive('align')
def align(context, n: int):
    """Advance the current address to the next multiple of n."""
    if n <= 0:
        context.reportError(f'Alignment must be positive: {n}')
        n = 1 # no alignment
    _ = context.symbols['_']
    mod = _ % n
    if mod > 0:
        context.symbols['_'] = _ - mod + n


@directive('print')
def printValues(context, value, *values):
    """Print values to the terminal, after the last pass."""
    context.printed.extend((value,) + values)


@directive('warning')
def warning(context, message: str):
    """Report a warning."""
    context.reportWarning(message)


@directive('error')
def error(context, message: str):
    """Report an error."""
    context.reportError(message)


@directive('assert')
def assertion(context, condition, message: str = 'Assertion failed'):
    """Report an error if the condition is false."""
    if not condition:
        context.reportError(message)


@directive('break')
def setBreakpoint(context, condition: str | None = None):
    """Set a VICE breakpoint at the current address, with an optional condition in VICE's format, e.g. "RL > $40"."""
    context.breakpoints.append((context.symbols['_'], condition))


BLOCK_DIRECTIVES = ('repeat', 'for', 'if', 'optional') # the directives that start a block
MAX_ITERATIONS = 0x10000 # a .for loop that runs longer is an error, e.g. over an endless iterator


@directive('repeat', raw=True)
def repeat(context, tokens: list, chunks: dict):
    """Start a repeat block: .repeat count. The lines up to .end are assembled count times.

    With a count of 0, the block is skipped. A .for loop gives a counter variable.
    """
    expression = lexer.join(tokens)
    count = evaluate.expression(expression, context)
    if type(count) is not int:
        context.reportError(f'Expected .repeat count: .repeat {expression}')
        return
    if count > 0:
        context.blockStack.append( ('repeat', count, context.readPointer()) )
    else:
        _skipBlock(context, chunks, 'repeat')


@directive('for', raw=True)
def forLoop(context, tokens: list, chunks: dict):
    """Start a for loop, as in Python: .for target in iterable, e.g. .for i in range(8).

    The lines up to .end are assembled for each value of the iterable, with the value assigned to the
    target: a name, or names to unpack each value into, e.g. .for name, value in colors.items().
    With no values, or after an error, the loop is skipped.
    """
    text = lexer.join(tokens)
    loop = _parseFor(text)
    if loop is None:
        context.reportError(f'Expected .for target in iterable: .for {text}')
        _skipBlock(context, chunks, 'for')
        return
    target, iterable = loop
    errors = len(context.errors)
    values = evaluate.expression(iterable, context)
    iterator = None
    if len(context.errors) == errors: # else the iterable failed, and is reported
        try:
            iterator = iter(values)
        except TypeError as exception:
            context.reportError(f'{evaluate.exceptionMessage(exception)}: "{iterable}"')
    if iterator is not None and _assignNext(context, target, iterator):
        context.blockStack.append( ('for', target, iterator, 0, context.readPointer()) )
    else:
        _skipBlock(context, chunks, 'for')


def _parseFor(text: str) -> tuple | None:
    """The target, as its syntax tree and its text, and the iterable of the text after .for, as Python parses it,
    e.g. "a, b" and "pairs" for "a, b in pairs", or None if it isn't a for loop with names as the target."""
    code = f'for {text}: pass'
    try:
        loop = ast.parse(code).body[0]
    except (SyntaxError, ValueError): # ValueError for a null byte, before Python 3.12
        return None
    if not isinstance(loop, ast.For) or not _isNames(loop.target):
        return None
    return (loop.target, ast.get_source_segment(code, loop.target)), ast.get_source_segment(code, loop.iter)


def _isNames(node) -> bool:
    """A target of names: a name, or a tuple or list of names, also nested, e.g. a, (b, c)."""
    if isinstance(node, ast.Name):
        return True
    return isinstance(node, (ast.Tuple, ast.List)) and all(_isNames(element) for element in node.elts)


def _assign(symbols, target, value):
    """Assign the value to the target's names, unpacking it as Python does, e.g. a, b = (1, 2). A name _ isn't
    assigned, as in Python it is a value that isn't used, and in nopa it is the current address."""
    if isinstance(target, ast.Name):
        if target.id != '_':
            symbols[target.id] = value
        return
    expected = len(target.elts)
    try:
        values = list(itertools.islice(iter(value), expected + 1)) # one more than expected, to know there are too many
    except TypeError:
        raise TypeError(f'cannot unpack non-iterable {type(value).__name__} object')
    if len(values) > expected:
        raise ValueError(f'too many values to unpack (expected {expected})')
    if len(values) < expected:
        raise ValueError(f'not enough values to unpack (expected {expected}, got {len(values)})')
    for name, item in zip(target.elts, values):
        _assign(symbols, name, item)


def _assignNext(context, target: tuple, iterator) -> bool:
    """Assign the next value of a for loop to its target. Returns False after the last value, or after an error."""
    node, text = target
    try:
        value = next(iterator)
    except StopIteration:
        return False
    except Exception as exception: # e.g. in a Python generator
        context.reportError(evaluate.exceptionMessage(exception))
        return False
    try:
        _assign(context.namespaceSymbols(), node, value)
    except (TypeError, ValueError) as exception:
        context.reportError(f'{evaluate.exceptionMessage(exception)}: "{text}"')
        return False
    return True


def _skipBlock(context, chunks: dict, name: str, stopAtElse: bool = False) -> str | None:
    """Skip lines, and continue after the matching .end, or .else if stopAtElse.

    Returns 'end' or 'else', where it continues, or None if there is none.
    """
    fileName, lineIndex = context.readPointer()
    lines = chunks[fileName]
    depth = 0
    for index in range(lineIndex + 1, len(lines)):
        line = lines[index]
        if len(line) >= 2 and line[1].string == ':': # after a label
            line = line[2:]
        if len(line) >= 2 and line[0].string == '.':
            if line[1].string in BLOCK_DIRECTIVES:
                depth += 1
            elif line[1].string == 'end' and depth > 0:
                depth -= 1
            elif line[1].string == 'end' or (line[1].string == 'else' and stopAtElse and depth == 0):
                context.jumpReadPointer( (fileName, index) ) # then advances past the .end or .else
                return line[1].string
    context.reportError(f'{name.capitalize()} without matching end')
    return None


@directive('end')
def end(context):
    """End the innermost block, and jump back if it has more rounds.

    The jump goes to the line that started the block, and as the read pointer
    then advances, assembly continues on the first line of the block.
    """
    if len(context.blockStack) == 0:
        context.reportError('End without matching repeat, for or if')
        return
    block = context.blockStack.pop()
    if block[0] == 'repeat':
        _endRepeat(context, *block[1:])
    elif block[0] == 'for':
        _endFor(context, *block[1:])


def _endRepeat(context, count: int, readPointer: tuple):
    """Jump back while there are repeats left."""
    if count > 1:
        context.blockStack.append( ('repeat', count - 1, readPointer) )
        context.jumpReadPointer(readPointer)


def _endFor(context, target: tuple, iterator, iterations: int, readPointer: tuple):
    """Assign the next value, and jump back while there are values left."""
    if iterations + 1 >= MAX_ITERATIONS:
        context.reportError(f'For loop did not end after {MAX_ITERATIONS} iterations')
        return
    if _assignNext(context, target, iterator):
        context.blockStack.append( ('for', target, iterator, iterations + 1, readPointer) )
        context.jumpReadPointer(readPointer)


@directive('if', raw=True)
def ifBlock(context, tokens: list, chunks: dict):
    """Start an if block: .if condition, e.g. .if a>5.

    If the condition is true, the lines up to .else or .end are assembled,
    otherwise the lines from .else to .end, if there is an .else.
    """
    if evaluate.expression(lexer.join(tokens), context):
        context.blockStack.append( ('if', False, context.readPointer()) )
    elif _skipBlock(context, chunks, 'if', stopAtElse=True) == 'else':
        context.blockStack.append( ('if', True, context.readPointer()) ) # in the .else lines


@directive('else', raw=True)
def elseBlock(context, tokens: list, chunks: dict):
    """Skip the lines from .else to .end, as the condition of the .if was true."""
    if len(context.blockStack) == 0 or context.blockStack[-1][0] != 'if':
        context.reportError('Else without matching if')
        return
    if context.blockStack[-1][1]: # already in the .else lines
        context.reportError('Else already used for this if')
        return
    context.blockStack.pop()
    _skipBlock(context, chunks, 'else')


def _globalLabels(lines: list) -> set:
    """The labels in the lines, local labels by their full names, except those in nested optional blocks."""
    labels, blocks = set(), []
    for line in lines:
        if len(line) >= 2 and line[1].string == ':':
            if 'optional' not in blocks:
                labels.add(line[0].string)
            line = line[2:]
        if len(line) >= 2 and line[0].string == '.':
            if line[1].string in BLOCK_DIRECTIVES:
                blocks.append(line[1].string)
            elif line[1].string == 'end':
                blocks.pop()
    return labels


@directive('optional', raw=True)
def optional(context, tokens: list, chunks: dict):
    """Start an optional block: like .if with ref() of each global label in the block."""
    start = context.readPointer()
    if _skipBlock(context, chunks, 'optional') is None:
        return
    fileName, end = context.readPointer()
    labels = {context.namespacedName(label) for label in _globalLabels(chunks[fileName][start[1] + 1:end])}
    if labels & context.lastReferences:
        context.jumpReadPointer(start)
        context.blockStack.append( ('optional', start) )


def reportOpenBlocks(context):
    """Report each block without .end at the line that started it, at the end of a pass."""
    for block in context.blockStack:
        context.pushReadPointer(block[-1])
        context.reportError(f'{block[0].capitalize()} without matching end')
        context.popReadPointer()


def _runPython(context, code: str, variables: dict | None = None, fileName: str = '<string>'):
    """Run Python code with the symbols as its variables, as the current namespace sees them, and note
    the names it uses as references, for ref() and .optional: a function that uses a label, e.g. return f,
    refers to it.

    With other variables, such as a namespace's module, the code can't see the symbols, so a name
    like init is always its own, never a label, and isn't a reference. Nothing is lost: the arguments
    of @namespace.f(label), and the code a generator returns, are noted where they are assembled.
    The file name, if the code is from a file, is where Python reports a syntax error.
    """
    compiled = compile(code, fileName, 'exec')
    if variables is None:
        context.noteReferences(compiled)
        exec(compiled, context.namespaceSymbols())
    else:
        exec(compiled, variables)


def _execute(context, code: str) -> bool:
    """Execute Python code. Returns False after reporting an error."""
    try:
        _runPython(context, code)
        return True
    except Exception as exception:
        context.reportError(f'Failed to execute python code: "{code}" ({type(exception).__name__}: {exception})')
        return False


@directive('python')
def python(context, code: str):
    """Execute Python code."""
    _execute(context, code)


def _namespaceModule(context, namespace: str) -> Namespace | None:
    """The module of a namespace, as a symbol, e.g. spr, or spr.util in a source file's namespace spr.
    Files imported into it share it, also in later passes, as other symbols. None, after reporting
    an error, if the name is another type of symbol."""
    name = context.namespacedName(namespace)
    module = context.symbols.get(name)
    if type(module) is not Namespace: # the first import into it, or the name is another symbol, which setSymbol() reports
        module = Namespace(name, context.symbols, context.builtinNames)
    return module if context.setSymbol(name, module) else None


def _importPyFile(context, path: str, fileName: str, namespace: str | None):
    """Run a .py file with the symbols as its variables, or in the module of a namespace."""
    variables = None # the symbols
    if namespace is not None:
        module = _namespaceModule(context, namespace)
        if module is None:
            return # the name is another type of symbol, so the file isn't run
        variables = module.__dict__
    try:
        with open(path) as f:
            _runPython(context, f.read(), variables, fileName)
    except Exception as exception:
        context.reportError(f'Failed to execute python code: "{fileName}" ({type(exception).__name__}: {exception})')


@directive('import')
def importFile(context, fileName: str, namespace: str | None = None):
    """Import a file: a .py file is executed, any other file is assembled as source code.

    A file can be imported into a namespace, a name that isn't a Python keyword or built-in, and doesn't
    start with _. A .py file then runs in a module of that name, so its names are used as namespace.name.
    Files imported into the same namespace share its module.
    """
    path = os.path.join(context.path, fileName)
    if namespace is not None and not lexer.isValidGlobalSymbolName(namespace):
        context.reportError(f'Namespace must be a name that isn\'t a Python keyword or built-in, and doesn\'t start with _: "{namespace}"')
    elif os.path.splitext(path)[1] == ".py":
        _importPyFile(context, path, fileName, namespace)
    elif not os.path.isfile(path):
        context.reportError(f'File not found: "{fileName}"')
    elif namespace is None or _namespaceModule(context, namespace) is not None: # else the name is another type of symbol
        context.advanceReadPointer()
        context.pushReadPointer( (path, 0), namespace )
        return False # the read pointer was moved


@directive('binary')
def binary(context, fileName: str, offset: int = 0, length: int | None = None):
    """Store the contents of a binary file, optionally from an offset, and with a length."""
    try:
        with open(os.path.join(context.path, fileName), 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        context.reportError(f'File not found: "{fileName}"')
        return

    for b in data[offset:None if length is None else offset+length]:
        context.store(b)
