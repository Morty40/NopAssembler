#! /usr/bin/env python3
"""The disassembler: turns a .prg or binary file into source that assembles to the same bytes."""

import errno

from . import assemble
from .cpu import CPU, CPU_6502, AddressMode


def _decode(data: bytes, start: int, address: int, cpu: CPU):
    """Decode the instruction at address: (instruction, mode, operand, size), or None if it isn't one.

    The operand of a branch is its destination address, also for bbr and bbs, whose zero page address is the second byte.
    """
    index = address - start
    if not 0 <= index < len(data) or not (found := cpu.instructionForOpcode(data[index])):
        return None
    instruction, mode = found
    size = mode.size
    if index + size > len(data):
        return None
    operand = int.from_bytes(data[index+1:index+size], 'little')
    if mode in (AddressMode.RELATIVE, AddressMode.ZERO_PAGE_RELATIVE): # a branch, with the offset in the last byte
        offset = data[index + size - 1]
        operand = address + size + (offset ^ 0x80) - 0x80 # signed offset, from the next instruction
        if not 0 <= operand <= 0xffff:
            return None
    return instruction, mode, operand, size


def _jumpsTo(instruction, mode) -> bool:
    """Check if the operand is a code address: a branch, jmp or jsr destination."""
    return mode in (AddressMode.RELATIVE, AddressMode.ZERO_PAGE_RELATIVE) or (instruction.mnemonic in ('jmp', 'jsr') and mode is AddressMode.ABSOLUTE)


def _monitorComment(address: int, data: bytes, instruction, mode, operand: int) -> str:
    """The instruction as a machine code monitor shows it: its address, bytes, the operand as a number, and
    its cycles, e.g. 1000  BD 20 D0  LDA $D020,X  4*. A '*' is a cycle that may be added, e.g. when a page is crossed."""
    digits = 4 if mode.size == 3 or mode is AddressMode.RELATIVE else 2
    operands = [f'${operand:0{digits}x}']
    if mode is AddressMode.ZERO_PAGE_RELATIVE: # bbr and bbs: the zero page address, then the branch destination
        operands.insert(0, f'${data[1]:02x}')
    text = f'{instruction.mnemonic} {mode.syntax(*operands)}'.strip()
    return f'{address:04x}  {data.hex(" "):<8}  {text:<14}  {instruction.cycles[mode]}'.upper() # 14 fits bbr3 $12,$1234


def _trace(data: bytes, start: int, entry: int, code: dict, used: set, cpu: CPU):
    """Find the new code that can be reached from entry, by following branches, jumps and subroutine calls.

    Returns {address: (instruction, mode, operand, size)}, or None if it isn't code: every path must end
    with jmp, bra, rts, rti or stp, or in known code, before it runs into an unknown opcode, brk, the middle of an
    instruction, or the end.
    """
    new: dict[int, tuple] = {}
    newUsed: set[int] = set()
    todo = [entry]
    while todo:
        address = todo.pop()
        while address not in code and address not in new:
            decoded = _decode(data, start, address, cpu)
            if decoded is None:
                return None
            instruction, mode, operand, size = decoded
            span = range(address, address + size)
            if instruction.mnemonic == 'brk' or not used.isdisjoint(span) or not newUsed.isdisjoint(span):
                return None
            new[address] = decoded
            newUsed.update(span)
            if _jumpsTo(instruction, mode) and start <= operand < start + len(data):
                todo.append(operand)
            if instruction.mnemonic in ('jmp', 'bra', 'rts', 'rti', 'stp'): # bra always branches, and stp stops the cpu
                break
            address += size
    return new


def _findCode(data: bytes, start: int, cpu: CPU) -> dict:
    """Find the code, by trying each byte that isn't code yet as the start of some.

    Returns {address: (instruction, mode, operand, size)} for each instruction.
    """
    code: dict[int, tuple] = {}
    used: set[int] = set()
    for address in range(start, start + len(data)):
        if address not in used and (new := _trace(data, start, address, code, used, cpu)):
            code.update(new)
            used.update(a for address, (*_, size) in new.items() for a in range(address, address + size))
    return code


def disassemble(data: bytes, start: int, names: dict[int, str] | None = None, cpu: CPU = CPU_6502) -> str:
    """Disassemble data at the start address into Nop Assembler source, with the instructions of the cpu.

    Code is found anywhere, other bytes are data, and branch and jump destinations get labels.
    names, {address: name} e.g. from a labels file, are used for their addresses instead.
    """
    end = start + len(data)
    code = _findCode(data, start, cpu)
    names = names or {}
    inside = {a for address, (*_, size) in code.items() for a in range(address + 1, address + size)}
    labels = {operand: f'l{operand:04x}' for instruction, mode, operand, _ in code.values()
              if _jumpsTo(instruction, mode) and operand in code}
    labels.update({address: name for address, name in names.items() if start <= address < end and address not in inside})
    assigned = {} # the names used by the code that aren't labels: outside the program, or inside an instruction

    def symbol(address: int, digits: int) -> str:
        """The label or name for an address, or else the address."""
        if address in labels:
            return labels[address]
        if address in names:
            assigned[address] = names[address]
            return names[address]
        return f'${address:0{digits}x}'

    def line(address: int, text: str) -> str:
        """A line of source at an address, indented, after its label if it has one."""
        indented = f'{"":<12}{text}'
        return f'{labels[address]}:\n{indented}' if address in labels else indented

    def byteList(values) -> str:
        """A .byte directive with the values."""
        return '.byte ' + ', '.join(f'${b:02x}' for b in values)

    lines: list[str | tuple[str, str]] = [''] # a line of code is (code, monitor comment)
    address, wasCode = start, None
    while address < end:
        if lines[-1] and (address in code) != wasCode:
            lines.append('') # between code and data
        wasCode = address in code
        comment = None # only for lines of code that are instructions, not .byte
        if wasCode:
            instruction, mode, operand, size = code[address]
            if mode.zeroPageMode in instruction.opcodes and operand < 0x100:
                text = byteList(data[address-start:address-start+size]) # would assemble as zero page
            else:
                comment = _monitorComment(address, data[address-start:address-start+size], instruction, mode, operand)
                if size == 3 or mode is AddressMode.RELATIVE:
                    operand = symbol(operand, 4)
                elif mode is AddressMode.IMMEDIATE:
                    operand = f'${operand:02x}'
                elif size == 2:
                    operand = symbol(operand, 2)
                operands = [operand]
                if mode is AddressMode.ZERO_PAGE_RELATIVE: # bbr and bbs: the zero page address, then the branch destination
                    operands.insert(0, symbol(data[address-start+1], 2))
                text = f'{instruction.mnemonic} {mode.syntax(*operands)}'.strip()
        else:
            # data up to the next code: 16 or more of the same byte, or else up to 16 bytes
            stop = next((a for a in range(address + 1, end) if a in code or a in labels), end)
            chunk = data[address-start:stop-start]
            size = len(chunk) - len(chunk.lstrip(chunk[:1])) # the bytes equal to the first
            if size >= 16:
                text = f'.bytefill {size}' + (f', "x: 0x{chunk[0]:02x}"' if chunk[0] else '')
            else:
                size = min(len(chunk), 16)
                text = byteList(chunk[:size])
        lines.append((line(address, text), comment) if comment else line(address, text))
        if wasCode and instruction.mnemonic in ('rts', 'rti'):
            lines.append('') # something new most likely starts here
        address += size

    def lastLength(code: str) -> int:
        """The length of the line of code, after its label if it has one."""
        return len(code) - code.rfind('\n') - 1

    # the monitor comments are aligned after the longest line of code, as a second column
    width = max((lastLength(entry[0]) for entry in lines if isinstance(entry, tuple)), default=0)
    source = [entry if isinstance(entry, str) else entry[0] + ' ' * (width - lastLength(entry[0])) + ' ; ' + entry[1]
              for entry in lines]

    header = ['; disassembled by Nop Assembler', '']
    header += [f'{name} = ${address:0{2 if address < 0x100 else 4}x}' for address, name in sorted(assigned.items())]
    header += [''] if assigned else []
    header += [f'{"":<12}.cpu CPU_{cpu.name}'] if cpu is not CPU_6502 else [] # the 6502 is the default
    header += [f'{"":<12}.org ${start:04x}']
    return '\n'.join(header + source).rstrip() + '\n'


def readLabels(labelsFile: str) -> dict:
    """Read a labels file, Python like the one -l writes, and return {address: name} for its int values.
    The first name is used for each address. Raises OSError if the file can't be read or executed."""
    symbols: dict[str, object] = {}
    try:
        with open(labelsFile) as f:
            exec(compile(f.read(), labelsFile, 'exec'), symbols)
    except OSError:
        raise
    except Exception as exception:
        raise OSError(errno.EINVAL, f'Invalid labels file ({type(exception).__name__}: {exception})', labelsFile)
    labels: dict[int, str] = {}
    for name, value in symbols.items():
        if type(value) is int and 0 <= value <= 0xffff:
            labels.setdefault(value, name)
    return labels


def disassembleFile(inFile: str, labelsFile: str | None = None, cpu: CPU = CPU_6502) -> str:
    """Disassemble a .prg file, which starts with its load address, or another binary file
    loaded at the default address, with the names from labelsFile, if given, and the instructions of the cpu. Returns the
    source. Raises OSError if a file can't be read.
    """
    with open(inFile, 'rb') as f:
        data = f.read()

    if inFile.lower().endswith('.prg') and len(data) >= 2:
        start, data = data[0] + data[1]*256, data[2:]
    else:
        start = assemble.DEFAULT_ORIGIN

    return disassemble(data, start, readLabels(labelsFile) if labelsFile else None, cpu)
