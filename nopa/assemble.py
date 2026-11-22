#! /usr/bin/env python3
"""The assembler: assembles source files into memory, in multiple passes."""

import keyword
import os
import glob

from . import directives
from . import evaluate
from . import generators
from . import instructions
from . import lexer
from . import text
from .context import Context
from .cpu import CPU, CPU_6502, CPU_65C02, CPU_R65C02, CPU_W65C02, CPU_DTV, isMnemonic, lo, hi

# max passes until all symbols should have been resolved
MAX_PASSES = 10

DEFAULT_ORIGIN = 0x1000 # the address when there is no .org

MAX_NESTING = 100 # imports and generators nested deeper are an error, e.g. a file that imports itself

TARGETS = ('c128', 'c16', 'c64', 'cx16', 'dtv', 'plus4', 'vic20') # the folders in imports/target


def _assembleAssignment(tokens: list, context: Context):
    """Assign the value of a Python expression to a symbol: name = expression.

    Upper case symbols are constants: once they have a value, they can't
    be assigned a different value. In a namespace, the symbol gets its
    namespaced name, e.g. speed in spr is spr.speed.
    """
    symbol = context.namespacedName(tokens[0].string)
    expression = lexer.join(tokens[2:])
    value, ok = evaluate.expression(expression, context)
    if ok: # None is a value too
        if symbol.rsplit('.', 1)[-1].isupper(): # the name, without a namespace, e.g. SPEED in spr.SPEED
            if symbol in context.symbols and context.symbols[symbol] != value:
                context.reportError(f'Constant "{symbol}" cannot be changed from {context.symbols[symbol]} to {value}')
                return # the constant keeps its value
        context.setSymbol(symbol, value)


def assembleFile(inFile: str, target: str | None = None, cpu: CPU | None = None,
                 defines: dict[str, str] | None = None) -> Context:
    """Assemble inFile. Returns the context of the last pass: memory, symbols, messages and errors,
    for the caller to use, e.g. to save the memory to a file. The target is one of TARGETS,
    whose imports are added to the generic ones. Each pass starts with the cpu, which .cpu can change:
    by default the target's CPU_DEFAULT_TYPE, or the 6502 without a target.
    The defines, {name: expression}, are assigned before the source, so upper case names are constants.
    Raises OSError if inFile can't be read, and ValueError for an unknown target.

    Passes are repeated until the output stops changing (max. MAX_PASSES), so
    labels can be used before they are defined.
    """
    if target is not None and target not in TARGETS:
        raise ValueError(f'Unknown target: {target}')

    path = os.path.dirname(inFile)

    symbols = {'lo': lo, 'hi': hi,
        'ENCODING_SCREEN_UPPER': text.ENCODING_SCREEN_UPPER,
        'ENCODING_SCREEN_MIXED': text.ENCODING_SCREEN_MIXED,
        'ENCODING_PETSCII_UPPER': text.ENCODING_PETSCII_UPPER,
        'ENCODING_PETSCII_MIXED': text.ENCODING_PETSCII_MIXED,
        'CPU_6502': CPU_6502,
        'CPU_65C02': CPU_65C02,
        'CPU_R65C02': CPU_R65C02,
        'CPU_W65C02': CPU_W65C02,
        'CPU_DTV': CPU_DTV,
        'SOURCE_FOLDER': path} # for generators that read files

    root = os.path.abspath(os.path.dirname(__file__))
    imports = sorted(glob.glob(os.path.join(root, 'imports/*.py')))
    if target:
        imports += sorted(glob.glob(os.path.join(root, 'imports/target', target, '*.py')))

    for filename in imports:
        with open(filename) as f:
            exec(compile(f.read(), filename, 'exec'), symbols) # the file name shows in tracebacks
    cpu = cpu or symbols.get('CPU_DEFAULT_TYPE', CPU_6502)

    lastMemory: dict[int, int] = {}
    lastReferences: set[str] = set()
    builtinNames: set[str] = set() # the symbols before the source, which code in a namespace sees, set in the first pass
    chunks = {} # the tokenized files and generated code, by name: tokenized once, for all passes

    for _ in range(MAX_PASSES):
        # a new context each pass, but symbols are kept from the last pass
        context = Context(symbols)
        context.currentAddress = DEFAULT_ORIGIN
        context.path = path
        context.cpu = cpu
        context.lastReferences = lastReferences
        symbols['has'] = lambda text: instructions.has(text, context)

        # the defines, assigned in each pass as if before the first line, so a variable starts with its value
        for index, (name, value) in enumerate((defines or {}).items()):
            context.pushReadPointer( ('<command-line>', index) ) # where an error is, as in gcc
            _assembleAssignment(lexer.tokenize(f'{name} = {value}')[:-1], context)
            context.popReadPointer()

        if not builtinNames: # in the first pass, after the -D defines and before the first line of source
            builtinNames = set(symbols)
        context.builtinNames = builtinNames
        context.pushReadPointer( (inFile, 0) )

        # assemble line by line, from the file on top of the read pointer stack
        while True:
            readPointer = context.readPointer()
            if readPointer is None: break
            if len(context.readPointerStack) > MAX_NESTING: # at the first line of the file nested too deep
                context.reportError(f'Imports and generators nested more than {MAX_NESTING} deep')
                context.popReadPointer() # back to the file that imported it, after the .import
                continue

            filename, lineIndex = readPointer

            if filename not in chunks:
                chunks[filename] = list(lexer.splitByNewline(lexer.tokenizeFile(filename)))

            allChunks = chunks[filename]

            if lineIndex < len(allChunks):

                lineTokens = allChunks[lineIndex]
                advance = True

                # label
                if len(lineTokens) >= 2 and lineTokens[1].string == ':':
                    label = lineTokens[0].string
                    if label.isupper():
                        context.reportError(f'Capitals are for constants, not labels: "{label}"')
                    elif label.startswith('_'):
                        context.reportError(f'Local label without a global label before it: "{label}"')
                    label = context.namespacedName(label) # the rules above are for the name as written, the rest for its full name
                    if label in context.labels:
                        context.reportError(f'Label was already defined: "{label}"')
                    context.setSymbol(label, context.currentAddress)
                    context.labels.add(label)
                    lineTokens = lineTokens[2:]

                if len(lineTokens) >= 1 and context.cpu.isMnemonic(lineTokens[0].string):
                    instructions.assemble(lineTokens, context)

                elif len(lineTokens) >= 3 and lineTokens[0].string.isidentifier() and not keyword.iskeyword(lineTokens[0].string) and lineTokens[1].string == '=':
                    _assembleAssignment(lineTokens, context)

                elif len(lineTokens) >= 2 and lineTokens[0].string == '.':
                    advance = directives.assemble(lineTokens, context, chunks)

                elif len(lineTokens) >= 2 and lineTokens[0].string == '@':
                    advance = generators.assemble(lineTokens, context, chunks)

                elif len(lineTokens) > 0 and isMnemonic(lineTokens[0].string): # an instruction of another cpu
                    context.reportError(f'Not an instruction of the {context.cpu.name}: "{lineTokens[0].string}", see .cpu and --cpu')

                elif len(lineTokens) > 0:
                    context.reportError('Invalid syntax')

                if advance:
                    context.advanceReadPointer()

            else:
                context.popReadPointer() # end of file, back to the importing file

        directives.reportOpenBlocks(context)

        # done when there are no errors, and the output and references are unchanged
        if len(context.errors) == 0 and context.memory == lastMemory and context.references == lastReferences:
            break

        # prepare for next pass
        lastMemory = dict(context.memory)
        lastReferences = context.references

    else: # no pass left, and the output still changed in the last one, with or without errors
        if not context.errors: # else they say what failed
            context.reportError(f'Failed to assemble: "{inFile}"')

    return context
