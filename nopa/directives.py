#! /usr/bin/env python3
"""The directives, such as .byte or .org, each a function in the DIRECTIVES table.

A directive's parameters declare the arguments it accepts, and their type
annotations the types, e.g. def org(context, address: int). Parameters
without an annotation accept any type.
"""

import inspect
import keyword
import os
import types
import typing
from collections.abc import Callable

from . import evaluate
from . import lexer
from . import text
from .context import Context
from .cpu import CPU


DIRECTIVES: dict[str, Callable[..., object]] = {} # directive name: function
_rawDirectives: set[str] = set() # directives that get their arguments as tokens, e.g. .for a=0, a<10, a+=1


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
        if expected is not inspect.Parameter.empty and any(type(v) not in allowed for v in values):
            return False
    return True


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
        context.store(evaluate.byteExpression(repr(value), context))


@directive('word')
def word(context, *values):
    """Store 16-bit words, low byte first."""
    for value in values:
        context.storeWord(evaluate.wordExpression(repr(value), context))


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
                context.store(evaluate.byteExpression(repr(o), context)) # your own encoding can have any value
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
    """Store a bit pattern, 8 bits per byte. 0 and space are 0 bits, 1 and # are 1 bits."""
    # todo: check length
    pattern = pattern.replace(' ', '0').replace('#', '1')
    for binString in [pattern[i:i+8] for i in range(0, len(pattern), 8)]:
        context.store(evaluate.byteExpression('0b'+binString, context))


@directive('bytefill')
def bytefill(context, n: int, function: str | None = None):
    """Store n bytes: zero, or the values of a lambda, e.g. "x: x * 2"."""
    _fill(context, n, function, context.store, evaluate.byteExpression)


@directive('wordfill')
def wordfill(context, n: int, function: str | None = None):
    """Store n words: zero, or the values of a lambda, e.g. "x: x * 2"."""
    _fill(context, n, function, context.storeWord, evaluate.wordExpression)


def _fill(context, n: int, function: str | None, store, valueExpression):
    """Store n values, using the store function, each checked by valueExpression."""
    f = evaluate.lambdaExpression(function, context) if function is not None else lambda x: 0
    for x in range(0, n):
        try:
            value = f(x)
        except Exception as exception:
            message = str(exception) # capitalize only the first letter, keeping the case of names
            context.reportError(f'{message[:1].upper()}{message[1:]}')
            value = 0
        store(valueExpression(repr(value), context))


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
MAX_ITERATIONS = 0x10000 # a .for loop that runs longer is an error, e.g. a condition that is never false


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
    """Start a for loop: .for initial, condition, step, e.g. .for a=0, a<10, a+=1.

    The initial and step are Python statements. While the condition is true,
    the lines up to .end are assembled. If it is false at the start, the
    loop is skipped.
    """
    parts = [lexer.join(part) for part in lexer.splitByComma(tokens)]
    if len(parts) != 3:
        context.reportError(f'Expected .for initial, condition, step: .for {lexer.join(tokens)}')
        return
    initial, condition, step = parts
    if not _execute(context, initial):
        return
    if evaluate.expression(condition, context):
        context.blockStack.append( ('for', condition, step, 0, context.readPointer()) )
    else:
        _skipBlock(context, chunks, 'for')


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


def _endFor(context, condition: str, step: str, iterations: int, readPointer: tuple):
    """Execute the step, and jump back while the condition is true."""
    if not _execute(context, step):
        return
    if iterations + 1 >= MAX_ITERATIONS:
        context.reportError(f'For loop did not end after {MAX_ITERATIONS} iterations')
        return
    if evaluate.expression(condition, context):
        context.blockStack.append( ('for', condition, step, iterations + 1, readPointer) )
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
    if _globalLabels(chunks[fileName][start[1] + 1:end]) & context.lastReferences:
        context.jumpReadPointer(start)
        context.blockStack.append( ('optional', start) )


def reportOpenBlocks(context):
    """Report each block without .end at the line that started it, at the end of a pass."""
    for block in context.blockStack:
        context.pushReadPointer(block[-1])
        context.reportError(f'{block[0].capitalize()} without matching end')
        context.popReadPointer()


def _runPython(context, code: str, variables: dict | None = None):
    """Run Python code with the symbols as its variables, or the given ones, and note the names it uses."""
    compiled = compile(code, '<string>', 'exec')
    context.noteReferences(compiled)
    exec(compiled, context.symbols if variables is None else variables)


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


@directive('import')
def importFile(context, fileName: str, namespace: str | None = None):
    """Import a file: a .py file is executed, any other file is assembled as source code.

    A .py file can be imported into a namespace, a name that doesn't start with _. It then runs in
    a module of that name, so its names are used as namespace.name. Files imported into the same
    namespace share its module.
    """
    path = os.path.join(context.path, fileName)
    if namespace is not None and os.path.splitext(path)[1] != ".py":
        context.reportError(f'Only a .py file can be imported into a namespace: "{fileName}"')
    elif namespace is not None and (not namespace.isidentifier() or keyword.iskeyword(namespace) or namespace.startswith('_')):
        context.reportError(f'Invalid namespace: "{namespace}"')
    elif os.path.splitext(path)[1] == ".py":
        variables = None # the symbols
        if namespace is not None:
            if namespace not in context.namespaces: # the first import into it in this pass
                context.namespaces[namespace] = types.ModuleType(namespace)
            module = context.namespaces[namespace]
            if not context.setSymbol(namespace, module):
                return # the name is another type of symbol, so the file isn't run
            variables = module.__dict__
        try:
            with open(path) as f:
                _runPython(context, f.read(), variables)
        except Exception as exception:
            context.reportError(f'Failed to execute python code: "{fileName}" ({type(exception).__name__}: {exception})')
    elif not os.path.isfile(path):
        context.reportError(f'File not found: "{fileName}"')
    else:
        context.advanceReadPointer()
        context.pushReadPointer( (path, 0) )
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
