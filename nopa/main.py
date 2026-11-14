#! /usr/bin/env python3
"""Nop Assembler command line: nopa <asmFile> -o <outFile>, or nopa -d <prgFile> -o <asmFile>"""

import argparse
import sys

from . import __version__
from . import assemble
from . import disassemble
from . import lexer
from .cpu import CPU_6502, CPU_65C02, CPU_R65C02, CPU_W65C02, isMnemonic, lo, hi
from .context import Context


def printMemoryUse(context: Context):
    """Print the memory range used, and a page map."""
    memory = context.memory
    if memory:
        first, last = min(memory), max(memory)
        print(f'Memory used: ${first:04x}-${last:04x} ({last - first + 1} bytes)')
    else:
        print('Memory used: None')

    pages = [0] * 256 # the number of bytes used in each page
    for address in memory:
        pages[address >> 8] += 1
    full = pages.count(256)
    print(f'Pages used: {full} full, {256 - full - pages.count(0)} partial')

    # one symbol for each page: unused, partly used, or full
    pageMap = ''.join('.' if used == 0 else '#' if used == 256 else '+' for used in pages)
    for i in range(16): # 16 pages per line
        print(f'${i:x}000: {pageMap[i * 16:(i + 1) * 16]}')


def sortedLabels(context: Context) -> list:
    """Return the (address, label) of each label, sorted by address."""
    return sorted((context.symbols[label], label) for label in context.labels)


def binary(context: Context) -> bytes:
    """Return a binary file: memory from the lowest address used to the highest, gaps as 0."""
    memory = context.memory
    return bytes(memory.get(address, 0) for address in range(min(memory), max(memory) + 1)) if memory else b''


def prg(context: Context) -> bytes:
    """Return a .prg file: the load address, the lowest address used or DEFAULT_ORIGIN, then the binary."""
    start = min(context.memory, default=assemble.DEFAULT_ORIGIN)
    return bytes([lo(start), hi(start)]) + binary(context)


FORMATS = {'prg': prg, 'bin': binary} # the formats of the output file


def pythonLabels(context: Context) -> str:
    """Return the labels as Python assignments, sorted by address."""
    return ''.join(f'{label} = 0x{address:04x}\n' for address, label in sortedLabels(context))


def viceMonitorCommands(context: Context) -> str:
    """Return the VICE monitor commands: the labels, sorted by address, then the breakpoints."""
    commands = [f'al C:{address:04x} .{label.replace(".", "_")}' for address, label in sortedLabels(context)] # spr_draw for spr.draw, as a VICE label is one word
    commands += [f'break C:{address:04x}' + (f' if {condition}' if condition else '') for address, condition in context.breakpoints]
    return ''.join(f'{command}\n' for command in commands)


CPUS = {'6502': CPU_6502, '65C02': CPU_65C02, 'R65C02': CPU_R65C02, 'W65C02': CPU_W65C02} # the choices of --cpu


def main():
    """Assemble or disassemble the file given on the command line. Exits with 1 on errors, 2 on incorrect arguments, and 130 after Ctrl-C."""
    parser = argparse.ArgumentParser(prog='nopa', description=f'Nop Assembler v{__version__}: a 6502/Python hybrid cross assembler for Commodore computers.')
    parser.add_argument('file', help='the source file to assemble, or with -d the .prg or binary file to disassemble')
    parser.add_argument('-d', '--disassemble', dest='disassemble', action='store_true', help='disassemble the file instead of assembling it')
    parser.add_argument('-o', '--output', dest='outFile', help='the file to write, or the source file when disassembling (default: print it)')
    parser.add_argument('--format', dest='outFormat', choices=list(FORMATS),
                        help='the format of the file to write: prg (default), with the load address, or bin, only the bytes')
    parser.add_argument('-t', '--target', dest='target', choices=assemble.TARGETS,
                        help='the target machine, whose symbols and generators are imported (default: none)')
    parser.add_argument('-l', '--labels', dest='labelsFile', help='the labels file, as Python assignments: written when assembling, read when disassembling')
    parser.add_argument('--cpu', dest='cpu', choices=list(CPUS), default='6502',
                        help='the cpu, and so the instructions: 6502 (default), 65C02, R65C02 or W65C02')
    parser.add_argument('-D', '--define', dest='defines', action='append', default=[], metavar='NAME[=VALUE]',
                        help='assign a symbol before the source, True without a value. Upper case names are constants')
    parser.add_argument('--vice', dest='viceFile', help='the VICE monitor commands file to write: labels and breakpoints')
    parser.add_argument('--version', action='version', version=f'Nop Assembler v{__version__} (c) Morten Perriard 2021-2026')
    arguments = parser.parse_args()
    if arguments.disassemble and arguments.viceFile:
        parser.error('--vice can only be used when assembling')
    if arguments.disassemble and arguments.outFormat:
        parser.error('--format can only be used when assembling')
    if arguments.disassemble and arguments.target:
        parser.error('--target can only be used when assembling')
    if arguments.disassemble and arguments.defines:
        parser.error('--define can only be used when assembling')
    defines = {}
    for define in arguments.defines:
        name, equals, value = define.partition('=')
        if not lexer.isValidGlobalSymbolName(name) or isMnemonic(name): # a mnemonic would make name = value an instruction
            parser.error(f'Invalid define: {define}')
        defines[name] = value if equals else 'True'
    cpu = CPUS[arguments.cpu]
    try:
        if arguments.disassemble:
            source = disassemble.disassembleFile(arguments.file, arguments.labelsFile, cpu)
            if arguments.outFile:
                with open(arguments.outFile, 'w') as f:
                    f.write(source)
            else:
                print(source, end='')
            anyErrors = False
        else:
            context = assemble.assembleFile(arguments.file, arguments.target, cpu, defines)
            for message in context.printed:
                print(message)
            sys.stdout.flush() # keep the order when stdout and stderr go to the same pipe or file
            for message in context.warnings + context.errors:
                print(message, file=sys.stderr)
            anyErrors = len(context.errors) > 0
            if not anyErrors:
                printMemoryUse(context)
                if arguments.outFile:
                    with open(arguments.outFile, 'wb') as f:
                        f.write(FORMATS[arguments.outFormat or 'prg'](context))
                if arguments.labelsFile:
                    with open(arguments.labelsFile, 'w') as f:
                        f.write(pythonLabels(context))
                if arguments.viceFile:
                    with open(arguments.viceFile, 'w') as f:
                        f.write(viceMonitorCommands(context))
    except OSError as exception:
        print(f'error: {exception.strerror}: "{exception.filename}"', file=sys.stderr)
        anyErrors = True
    except KeyboardInterrupt:
        print('error: Interrupted', file=sys.stderr)
        sys.exit(130) # the usual exit code after Ctrl-C
    sys.exit(1 if anyErrors else 0)


if __name__ == '__main__':
   main()
