#! /usr/bin/env python3
"""The 6502 instructions: assembles an instruction line, e.g. lda #1."""

from . import evaluate
from . import lexer
from .context import Context
from .cpu import CPU_6502, AddressMode, isMnemonic, lo, hi


def _branchOffset(destination: int, size: int, context: Context) -> int:
    """The offset of a branch to the destination, as a signed byte, counted from the address after the instruction."""
    dist = destination - context.symbols['_'] - size
    if dist < -128 or dist > 127: # branch is out of range (signed byte)
        context.reportError(f'Branch destination out of range [-128..127]: {dist}')
        dist = 0
    return dist & 0xff


def has(text: str, context: Context) -> bool:
    """Check if an instruction, e.g. lax $12, would assemble on the current cpu, without storing anything.

    Its errors and warnings are not reported, but a word that is an instruction on no cpu is an error.
    """
    tokens = lexer.tokenize(text)[:-1]
    mnemonic = tokens[0].string
    if not isMnemonic(mnemonic): # on no cpu, so a typo that shouldn't choose a code path
        context.reportError(f'Not an instruction: "{mnemonic}"')
        return False

    if not context.cpu.isMnemonic(mnemonic):
        return False

    saved = context.memory, context.errors, context.warnings, context.symbols['_'], set(context.references)
    context.memory, context.errors, context.warnings = {}, [], []
    assemble(tokens, context)
    assembles = not context.errors
    context.memory, context.errors, context.warnings, context.symbols['_'], context.references = saved
    return assembles


def assemble(tokens: list, context: Context):
    """Assemble an instruction, with the address mode given by the operand.

    Zero page modes are chosen for addresses below $100.
    """
    mnemonic = tokens[0].string
    operand = lexer.join(tokens[1:])

    instruction = context.cpu.instructionWithMnemonic(mnemonic)
    assert instruction is not None # the caller checked that it is a mnemonic
    opcodes = instruction.opcodes

    data = []

    if AddressMode.ACCUMULATOR in opcodes and not operand:
        data = [opcodes[AddressMode.ACCUMULATOR]]

    elif AddressMode.IMPLIED in opcodes and not operand:
        data = [opcodes[AddressMode.IMPLIED]]

    elif AddressMode.IMMEDIATE in opcodes and operand.startswith('#'):
        v = evaluate.byteExpression(operand[1:], context)
        data = [opcodes[AddressMode.IMMEDIATE], v]

    elif AddressMode.ZERO_PAGE_INDIRECT_X in opcodes and operand.startswith('(') and operand.endswith(',x)'):
        v = evaluate.byteExpression(operand[1:-3], context)
        data = [opcodes[AddressMode.ZERO_PAGE_INDIRECT_X], v]

    elif AddressMode.ABSOLUTE_INDIRECT_X in opcodes and operand.startswith('(') and operand.endswith(',x)'): # 65C02
        v = evaluate.wordExpression(operand[1:-3], context)
        data = [opcodes[AddressMode.ABSOLUTE_INDIRECT_X], lo(v), hi(v)]

    elif AddressMode.ZERO_PAGE_INDIRECT_Y in opcodes and operand.startswith('(') and operand.endswith('),y'):
        v = evaluate.byteExpression(operand[1:-3], context)
        data = [opcodes[AddressMode.ZERO_PAGE_INDIRECT_Y], v]

    elif AddressMode.ABSOLUTE_INDIRECT in opcodes and operand.startswith('(') and operand.endswith(')'):
        v = evaluate.wordExpression(operand[1:-1], context)
        if lo(v) == 0xff and context.cpu is CPU_6502: # the 6502 reads the high byte from $xx00, not the next page
            context.reportWarning(f'Indirect address located on page boundary: ${v:04x}')
        data = [opcodes[AddressMode.ABSOLUTE_INDIRECT], lo(v), hi(v)]

    elif AddressMode.ZERO_PAGE_INDIRECT in opcodes and operand.startswith('(') and operand.endswith(')'): # 65C02
        v = evaluate.byteExpression(operand[1:-1], context)
        data = [opcodes[AddressMode.ZERO_PAGE_INDIRECT], v]

    elif AddressMode.RELATIVE in opcodes: # TODO: give warning about branching across page boundary
        v = evaluate.wordExpression(operand, context)
        data = [opcodes[AddressMode.RELATIVE], _branchOffset(v, 2, context)]

    elif AddressMode.ZERO_PAGE_RELATIVE in opcodes and len(lexer.splitByComma(tokens[1:])) == 2: # Rockwell and WDC
        zeroPage, destination = (lexer.join(part) for part in lexer.splitByComma(tokens[1:])) # e.g. bbr3 $12,label
        z = evaluate.byteExpression(zeroPage, context)
        v = evaluate.wordExpression(destination, context)
        data = [opcodes[AddressMode.ZERO_PAGE_RELATIVE], z, _branchOffset(v, 3, context)]

    elif (AddressMode.ZERO_PAGE_X in opcodes or AddressMode.ABSOLUTE_X in opcodes) and operand.endswith(',x'):
        v = evaluate.wordExpression(operand[:-2], context)
        if AddressMode.ZERO_PAGE_X in opcodes and hi(v) == 0:
            data = [opcodes[AddressMode.ZERO_PAGE_X], lo(v)]
        elif AddressMode.ABSOLUTE_X in opcodes:
            data = [opcodes[AddressMode.ABSOLUTE_X], lo(v), hi(v)]

    elif (AddressMode.ZERO_PAGE_Y in opcodes or AddressMode.ABSOLUTE_Y in opcodes) and operand.endswith(',y'):
        v = evaluate.wordExpression(operand[:-2], context)
        if AddressMode.ZERO_PAGE_Y in opcodes and hi(v) == 0:
            data = [opcodes[AddressMode.ZERO_PAGE_Y], lo(v)]
        elif AddressMode.ABSOLUTE_Y in opcodes:
            data = [opcodes[AddressMode.ABSOLUTE_Y], lo(v), hi(v)]

    elif (AddressMode.ZERO_PAGE in opcodes or AddressMode.ABSOLUTE in opcodes) and operand:
        v = evaluate.wordExpression(operand, context)
        if AddressMode.ZERO_PAGE in opcodes and hi(v) == 0:
            data = [opcodes[AddressMode.ZERO_PAGE], lo(v)]
        elif AddressMode.ABSOLUTE in opcodes:
            data = [opcodes[AddressMode.ABSOLUTE], lo(v), hi(v)]

    if len(data) <= 0:
        context.reportError(f'Unknown instruction or address mode: {mnemonic} {operand}')

    # store the bytes
    for b in data:
        context.store(b)
