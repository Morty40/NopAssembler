#! /usr/bin/env python3
"""The generators: Python code that returns assembly code, e.g. @nop(3)."""

import re

from . import evaluate
from . import lexer
from .context import Context


def assemble(tokens: list, context: Context, chunks: dict) -> bool:
    """Assemble the code returned by a generator: @function(arguments).

    The generated code is added to chunks, the tokenized files, and assembled
    like an imported file. Local labels get their own scope for each call, named after the generator.
    Returns False, as the read pointer is moved to the generated code.
    """
    generator = lexer.join(tokens[1:])
    value = evaluate.expression(generator, context)
    if type(value) is not str:
        context.reportError(f'Generator must return a string, not {type(value).__name__}')
        value = '' # no code to assemble

    context.advanceReadPointer()

    (fileName, lineIndex) = context.readPointer()
    generatorId = f"{fileName}:{lineIndex} @{generator}"
    # local labels are named after the generator and its call count, e.g. _loop in the 2nd @ldax() is ldax2_loop
    match = re.match(r'[A-Za-z_][\w.]*', generator)
    name = match.group().split('.')[-1] if match else 'gen'
    context.generatorCounts[name] = context.generatorCounts.get(name, 0) + 1
    generatedTokens = lexer.translateLocalLabels(lexer.tokenize(value), f'{name}{context.generatorCounts[name]}')
    chunks[generatorId] = list(lexer.splitByNewline(generatedTokens))

    context.pushReadPointer( (generatorId, 0) )

    return False # don't advance
