#! /usr/bin/env python3
"""The 6502 instruction set: the opcode of each instruction in each address mode."""

from enum import Enum, unique
import re


# the low and high byte of a 16-bit value, the 6502 stores words low byte first
def lo(x):
    """The low byte."""
    return x&0xff


def hi(x):
    """The high byte."""
    return (x>>8)&0xff


@unique
class AddressMode(Enum):
    """The address modes of the 6502, the two the 65C02 adds, and the one the Rockwell and WDC 65C02 add. Each has
    the operand syntax, see syntax(), and the size of an instruction: the opcode, and its operand bytes."""

    ABSOLUTE             = ('absolute', 3)
    ABSOLUTE_X           = ('absolute,x', 3)
    ABSOLUTE_Y           = ('absolute,y', 3)
    ABSOLUTE_INDIRECT    = ('(absolute)', 3)
    ABSOLUTE_INDIRECT_X  = ('(absolute,x)', 3)  # 65C02, jmp only
    ACCUMULATOR          = ('accumulator', 1)
    IMMEDIATE            = ('immediate', 2)
    IMPLIED              = ('implied', 1)
    RELATIVE             = ('relative', 2)
    ZERO_PAGE            = ('zeropage', 2)
    ZERO_PAGE_X          = ('zeropage,x', 2)
    ZERO_PAGE_Y          = ('zeropage,y', 2)
    ZERO_PAGE_INDIRECT   = ('(zeropage)', 2)    # 65C02
    ZERO_PAGE_INDIRECT_X = ('(zeropage,x)', 2)
    ZERO_PAGE_INDIRECT_Y = ('(zeropage),y', 2)
    ZERO_PAGE_RELATIVE   = ('zeropage,relative', 3) # Rockwell and WDC 65C02, bbr and bbs only

    def __init__(self, template: str, size: int):
        self.template = template # the operand syntax, with each operand as a word, e.g. (zeropage),y
        self.size = size

    @property
    def zeroPageMode(self):
        """The zero page mode the assembler chooses instead of this mode for addresses below $100, or None."""
        return {AddressMode.ABSOLUTE: AddressMode.ZERO_PAGE,
                AddressMode.ABSOLUTE_X: AddressMode.ZERO_PAGE_X,
                AddressMode.ABSOLUTE_Y: AddressMode.ZERO_PAGE_Y}.get(self)

    def syntax(self, *operands: str) -> str:
        """Write the operands in this mode, e.g. '($10),y' for ZERO_PAGE_INDIRECT_Y and '$10',
        and '$10,label' for ZERO_PAGE_RELATIVE and '$10', 'label'."""
        if self in (AddressMode.IMPLIED, AddressMode.ACCUMULATOR):
            return ''
        if self is AddressMode.IMMEDIATE:
            return '#' + operands[0]
        remaining = iter(operands)
        return re.sub(r'zeropage|absolute|relative', lambda _: next(remaining), self.template) # e.g. (zeropage),y


class Instruction:
    """An instruction mnemonic, and its opcode for each address mode it supports."""

    def __init__(self, mnemonic, **modes):
        """Each address mode is given by name, with its opcode and cycles, e.g. IMMEDIATE=(0xa9, '2').
        A '*' in the cycles is a cycle that may be added, e.g. when a page is crossed."""
        self.mnemonic = mnemonic
        self.opcodes = {AddressMode[mode]: opcode for mode, (opcode, cycles) in modes.items()}
        self.cycles = {AddressMode[mode]: cycles for mode, (opcode, cycles) in modes.items()}


# the 56 instructions documented by MOS for the 6502, the same on all 6502 family cpus. Some of the
# opcodes they leave unused are the "illegal" instructions below, and on the 65C02 the CMOS instructions.
# Each address mode has its opcode and cycles, with a '*' for each cycle that may be added: when indexing
# crosses a page, when a branch is taken, or when it goes to another page
_documentedInstructionSet = {
    Instruction('adc', ABSOLUTE=(0x6d, '4'),
                       ABSOLUTE_X=(0x7d, '4*'),
                       ABSOLUTE_Y=(0x79, '4*'),
                       IMMEDIATE=(0x69, '2'),
                       ZERO_PAGE=(0x65, '3'),
                       ZERO_PAGE_X=(0x75, '4'),
                       ZERO_PAGE_INDIRECT_X=(0x61, '6'),
                       ZERO_PAGE_INDIRECT_Y=(0x71, '5*')),
    Instruction('and', ABSOLUTE=(0x2d, '4'),
                       ABSOLUTE_X=(0x3d, '4*'),
                       ABSOLUTE_Y=(0x39, '4*'),
                       IMMEDIATE=(0x29, '2'),
                       ZERO_PAGE=(0x25, '3'),
                       ZERO_PAGE_X=(0x35, '4'),
                       ZERO_PAGE_INDIRECT_X=(0x21, '6'),
                       ZERO_PAGE_INDIRECT_Y=(0x31, '5*')),
    Instruction('asl', ABSOLUTE=(0x0e, '6'),
                       ABSOLUTE_X=(0x1e, '7'),
                       ACCUMULATOR=(0x0a, '2'),
                       ZERO_PAGE=(0x06, '5'),
                       ZERO_PAGE_X=(0x16, '6')),
    Instruction('bcc', RELATIVE=(0x90, '2**')),
    Instruction('bcs', RELATIVE=(0xb0, '2**')),
    Instruction('beq', RELATIVE=(0xf0, '2**')),
    Instruction('bit', ABSOLUTE=(0x2c, '4'),
                       ZERO_PAGE=(0x24, '3')),
    Instruction('bmi', RELATIVE=(0x30, '2**')),
    Instruction('bne', RELATIVE=(0xd0, '2**')),
    Instruction('bpl', RELATIVE=(0x10, '2**')),
    Instruction('brk', IMPLIED=(0x00, '7')),
    Instruction('bvc', RELATIVE=(0x50, '2**')),
    Instruction('bvs', RELATIVE=(0x70, '2**')),
    Instruction('clc', IMPLIED=(0x18, '2')),
    Instruction('cld', IMPLIED=(0xd8, '2')),
    Instruction('cli', IMPLIED=(0x58, '2')),
    Instruction('clv', IMPLIED=(0xb8, '2')),
    Instruction('cmp', ABSOLUTE=(0xcd, '4'),
                       ABSOLUTE_X=(0xdd, '4*'),
                       ABSOLUTE_Y=(0xd9, '4*'),
                       IMMEDIATE=(0xc9, '2'),
                       ZERO_PAGE=(0xc5, '3'),
                       ZERO_PAGE_X=(0xd5, '4'),
                       ZERO_PAGE_INDIRECT_X=(0xc1, '6'),
                       ZERO_PAGE_INDIRECT_Y=(0xd1, '5*')),
    Instruction('cpx', ABSOLUTE=(0xec, '4'),
                       IMMEDIATE=(0xe0, '2'),
                       ZERO_PAGE=(0xe4, '3')),
    Instruction('cpy', ABSOLUTE=(0xcc, '4'),
                       IMMEDIATE=(0xc0, '2'),
                       ZERO_PAGE=(0xc4, '3')),
    Instruction('dec', ABSOLUTE=(0xce, '6'),
                       ABSOLUTE_X=(0xde, '7'),
                       ZERO_PAGE=(0xc6, '5'),
                       ZERO_PAGE_X=(0xd6, '6')),
    Instruction('dex', IMPLIED=(0xca, '2')),
    Instruction('dey', IMPLIED=(0x88, '2')),
    Instruction('eor', ABSOLUTE=(0x4d, '4'),
                       ABSOLUTE_X=(0x5d, '4*'),
                       ABSOLUTE_Y=(0x59, '4*'),
                       IMMEDIATE=(0x49, '2'),
                       ZERO_PAGE=(0x45, '3'),
                       ZERO_PAGE_X=(0x55, '4'),
                       ZERO_PAGE_INDIRECT_X=(0x41, '6'),
                       ZERO_PAGE_INDIRECT_Y=(0x51, '5*')),
    Instruction('inc', ABSOLUTE=(0xee, '6'),
                       ABSOLUTE_X=(0xfe, '7'),
                       ZERO_PAGE=(0xe6, '5'),
                       ZERO_PAGE_X=(0xf6, '6')),
    Instruction('inx', IMPLIED=(0xe8, '2')),
    Instruction('iny', IMPLIED=(0xc8, '2')),
    Instruction('jmp', ABSOLUTE=(0x4c, '3'),
                       ABSOLUTE_INDIRECT=(0x6c, '5')),
    Instruction('jsr', ABSOLUTE=(0x20, '6')),
    Instruction('lda', ABSOLUTE=(0xad, '4'),
                       ABSOLUTE_X=(0xbd, '4*'),
                       ABSOLUTE_Y=(0xb9, '4*'),
                       IMMEDIATE=(0xa9, '2'),
                       ZERO_PAGE=(0xa5, '3'),
                       ZERO_PAGE_X=(0xb5, '4'),
                       ZERO_PAGE_INDIRECT_X=(0xa1, '6'),
                       ZERO_PAGE_INDIRECT_Y=(0xb1, '5*')),
    Instruction('ldx', ABSOLUTE=(0xae, '4'),
                       ABSOLUTE_Y=(0xbe, '4*'),
                       IMMEDIATE=(0xa2, '2'),
                       ZERO_PAGE=(0xa6, '3'),
                       ZERO_PAGE_Y=(0xb6, '4')),
    Instruction('ldy', ABSOLUTE=(0xac, '4'),
                       ABSOLUTE_X=(0xbc, '4*'),
                       IMMEDIATE=(0xa0, '2'),
                       ZERO_PAGE=(0xa4, '3'),
                       ZERO_PAGE_X=(0xb4, '4')),
    Instruction('lsr', ABSOLUTE=(0x4e, '6'),
                       ABSOLUTE_X=(0x5e, '7'),
                       ACCUMULATOR=(0x4a, '2'),
                       ZERO_PAGE=(0x46, '5'),
                       ZERO_PAGE_X=(0x56, '6')),
    Instruction('nop', IMPLIED=(0xea, '2')),
    Instruction('ora', ABSOLUTE=(0x0d, '4'),
                       ABSOLUTE_X=(0x1d, '4*'),
                       ABSOLUTE_Y=(0x19, '4*'),
                       IMMEDIATE=(0x09, '2'),
                       ZERO_PAGE=(0x05, '3'),
                       ZERO_PAGE_X=(0x15, '4'),
                       ZERO_PAGE_INDIRECT_X=(0x01, '6'),
                       ZERO_PAGE_INDIRECT_Y=(0x11, '5*')),
    Instruction('pha', IMPLIED=(0x48, '3')),
    Instruction('php', IMPLIED=(0x08, '3')),
    Instruction('pla', IMPLIED=(0x68, '4')),
    Instruction('plp', IMPLIED=(0x28, '4')),
    Instruction('rol', ABSOLUTE=(0x2e, '6'),
                       ABSOLUTE_X=(0x3e, '7'),
                       ACCUMULATOR=(0x2a, '2'),
                       ZERO_PAGE=(0x26, '5'),
                       ZERO_PAGE_X=(0x36, '6')),
    Instruction('ror', ABSOLUTE=(0x6e, '6'),
                       ABSOLUTE_X=(0x7e, '7'),
                       ACCUMULATOR=(0x6a, '2'),
                       ZERO_PAGE=(0x66, '5'),
                       ZERO_PAGE_X=(0x76, '6')),
    Instruction('rti', IMPLIED=(0x40, '6')),
    Instruction('rts', IMPLIED=(0x60, '6')),
    Instruction('sbc', ABSOLUTE=(0xed, '4'),
                       ABSOLUTE_X=(0xfd, '4*'),
                       ABSOLUTE_Y=(0xf9, '4*'),
                       IMMEDIATE=(0xe9, '2'),
                       ZERO_PAGE=(0xe5, '3'),
                       ZERO_PAGE_X=(0xf5, '4'),
                       ZERO_PAGE_INDIRECT_X=(0xe1, '6'),
                       ZERO_PAGE_INDIRECT_Y=(0xf1, '5*')),
    Instruction('sec', IMPLIED=(0x38, '2')),
    Instruction('sed', IMPLIED=(0xf8, '2')),
    Instruction('sei', IMPLIED=(0x78, '2')),
    Instruction('sta', ABSOLUTE=(0x8d, '4'),
                       ABSOLUTE_X=(0x9d, '5'),
                       ABSOLUTE_Y=(0x99, '5'),
                       ZERO_PAGE=(0x85, '3'),
                       ZERO_PAGE_X=(0x95, '4'),
                       ZERO_PAGE_INDIRECT_X=(0x81, '6'),
                       ZERO_PAGE_INDIRECT_Y=(0x91, '6')),
    Instruction('stx', ABSOLUTE=(0x8e, '4'),
                       ZERO_PAGE=(0x86, '3'),
                       ZERO_PAGE_Y=(0x96, '4')),
    Instruction('sty', ABSOLUTE=(0x8c, '4'),
                       ZERO_PAGE=(0x84, '3'),
                       ZERO_PAGE_X=(0x94, '4')),
    Instruction('tax', IMPLIED=(0xaa, '2')),
    Instruction('tay', IMPLIED=(0xa8, '2')),
    Instruction('tsx', IMPLIED=(0xba, '2')),
    Instruction('txa', IMPLIED=(0x8a, '2')),
    Instruction('txs', IMPLIED=(0x9a, '2')),
    Instruction('tya', IMPLIED=(0x98, '2'))}

# the "illegal" instructions that work the same on all 6510, 8500 and 8502 cpus. Left out are anc 0x2b
# and usbc 0xeb, which do the same as anc 0x0b and sbc 0xe9, the nops, which would conflict with nop, and
# the unstable ane, lxa, sha, shx, shy and tas, which depend on the cpu, its temperature, or dma
_illegalInstructionSet = {
    Instruction('alr', IMMEDIATE=(0x4b, '2')),
    Instruction('anc', IMMEDIATE=(0x0b, '2')),
    Instruction('arr', IMMEDIATE=(0x6b, '2')),
    Instruction('dcp', ABSOLUTE=(0xcf, '6'),
                       ABSOLUTE_X=(0xdf, '7'),
                       ABSOLUTE_Y=(0xdb, '7'),
                       ZERO_PAGE=(0xc7, '5'),
                       ZERO_PAGE_X=(0xd7, '6'),
                       ZERO_PAGE_INDIRECT_X=(0xc3, '8'),
                       ZERO_PAGE_INDIRECT_Y=(0xd3, '8')),
    Instruction('isc', ABSOLUTE=(0xef, '6'),
                       ABSOLUTE_X=(0xff, '7'),
                       ABSOLUTE_Y=(0xfb, '7'),
                       ZERO_PAGE=(0xe7, '5'),
                       ZERO_PAGE_X=(0xf7, '6'),
                       ZERO_PAGE_INDIRECT_X=(0xe3, '8'),
                       ZERO_PAGE_INDIRECT_Y=(0xf3, '8')),
    Instruction('las', ABSOLUTE_Y=(0xbb, '4*')),
    Instruction('lax', ABSOLUTE=(0xaf, '4'),
                       ABSOLUTE_Y=(0xbf, '4*'),
                       ZERO_PAGE=(0xa7, '3'),
                       ZERO_PAGE_Y=(0xb7, '4'),
                       ZERO_PAGE_INDIRECT_X=(0xa3, '6'),
                       ZERO_PAGE_INDIRECT_Y=(0xb3, '5*')),
    Instruction('rla', ABSOLUTE=(0x2f, '6'),
                       ABSOLUTE_X=(0x3f, '7'),
                       ABSOLUTE_Y=(0x3b, '7'),
                       ZERO_PAGE=(0x27, '5'),
                       ZERO_PAGE_X=(0x37, '6'),
                       ZERO_PAGE_INDIRECT_X=(0x23, '8'),
                       ZERO_PAGE_INDIRECT_Y=(0x33, '8')),
    Instruction('rra', ABSOLUTE=(0x6f, '6'),
                       ABSOLUTE_X=(0x7f, '7'),
                       ABSOLUTE_Y=(0x7b, '7'),
                       ZERO_PAGE=(0x67, '5'),
                       ZERO_PAGE_X=(0x77, '6'),
                       ZERO_PAGE_INDIRECT_X=(0x63, '8'),
                       ZERO_PAGE_INDIRECT_Y=(0x73, '8')),
    Instruction('sax', ABSOLUTE=(0x8f, '4'),
                       ZERO_PAGE=(0x87, '3'),
                       ZERO_PAGE_Y=(0x97, '4'),
                       ZERO_PAGE_INDIRECT_X=(0x83, '6')),
    Instruction('sbx', IMMEDIATE=(0xcb, '2')),
    Instruction('slo', ABSOLUTE=(0x0f, '6'),
                       ABSOLUTE_X=(0x1f, '7'),
                       ABSOLUTE_Y=(0x1b, '7'),
                       ZERO_PAGE=(0x07, '5'),
                       ZERO_PAGE_X=(0x17, '6'),
                       ZERO_PAGE_INDIRECT_X=(0x03, '8'),
                       ZERO_PAGE_INDIRECT_Y=(0x13, '8')),
    Instruction('sre', ABSOLUTE=(0x4f, '6'),
                       ABSOLUTE_X=(0x5f, '7'),
                       ABSOLUTE_Y=(0x5b, '7'),
                       ZERO_PAGE=(0x47, '5'),
                       ZERO_PAGE_X=(0x57, '6'),
                       ZERO_PAGE_INDIRECT_X=(0x43, '8'),
                       ZERO_PAGE_INDIRECT_Y=(0x53, '8'))}

# the instructions the 65C02 adds to the documented 6502 ones: new instructions, and new address modes for some
# of the 6502's, to add to their 6502 modes. The 6502 modes whose cycles it changes are declared again, with the
# same opcodes. The Rockwell and WDC bit instructions are in _rockwellInstructionSet, and WDC's wai and stp in _wdcInstructionSet
_cmosInstructionSet = {
    Instruction('adc', ABSOLUTE=(0x6d, '4*'),           # one more cycle in decimal mode, in every mode
                       ABSOLUTE_X=(0x7d, '4**'),
                       ABSOLUTE_Y=(0x79, '4**'),
                       IMMEDIATE=(0x69, '2*'),
                       ZERO_PAGE=(0x65, '3*'),
                       ZERO_PAGE_X=(0x75, '4*'),
                       ZERO_PAGE_INDIRECT=(0x72, '5*'),
                       ZERO_PAGE_INDIRECT_X=(0x61, '6*'),
                       ZERO_PAGE_INDIRECT_Y=(0x71, '5**')),
    Instruction('and', ZERO_PAGE_INDIRECT=(0x32, '5')),
    Instruction('asl', ABSOLUTE_X=(0x1e, '6*')),        # abs,x takes 7 cycles on the 6502, and here only when a page is crossed
    Instruction('bit', ABSOLUTE_X=(0x3c, '4*'),
                       IMMEDIATE=(0x89, '2'),
                       ZERO_PAGE_X=(0x34, '4')),
    Instruction('bra', RELATIVE=(0x80, '3*')),
    Instruction('cmp', ZERO_PAGE_INDIRECT=(0xd2, '5')),
    Instruction('dec', ACCUMULATOR=(0x3a, '2')),
    Instruction('eor', ZERO_PAGE_INDIRECT=(0x52, '5')),
    Instruction('inc', ACCUMULATOR=(0x1a, '2')),
    Instruction('jmp', ABSOLUTE_INDIRECT=(0x6c, '6'),   # ($1234) takes one cycle more than on the 6502, which fixes its page boundary bug
                       ABSOLUTE_INDIRECT_X=(0x7c, '6')),
    Instruction('lda', ZERO_PAGE_INDIRECT=(0xb2, '5')),
    Instruction('lsr', ABSOLUTE_X=(0x5e, '6*')),        # abs,x takes 7 cycles on the 6502, and here only when a page is crossed
    Instruction('ora', ZERO_PAGE_INDIRECT=(0x12, '5')),
    Instruction('phx', IMPLIED=(0xda, '3')),
    Instruction('phy', IMPLIED=(0x5a, '3')),
    Instruction('plx', IMPLIED=(0xfa, '4')),
    Instruction('ply', IMPLIED=(0x7a, '4')),
    Instruction('rol', ABSOLUTE_X=(0x3e, '6*')),        # abs,x takes 7 cycles on the 6502, and here only when a page is crossed
    Instruction('ror', ABSOLUTE_X=(0x7e, '6*')),        # abs,x takes 7 cycles on the 6502, and here only when a page is crossed
    Instruction('sbc', ABSOLUTE=(0xed, '4*'),           # one more cycle in decimal mode, in every mode
                       ABSOLUTE_X=(0xfd, '4**'),
                       ABSOLUTE_Y=(0xf9, '4**'),
                       IMMEDIATE=(0xe9, '2*'),
                       ZERO_PAGE=(0xe5, '3*'),
                       ZERO_PAGE_X=(0xf5, '4*'),
                       ZERO_PAGE_INDIRECT=(0xf2, '5*'),
                       ZERO_PAGE_INDIRECT_X=(0xe1, '6*'),
                       ZERO_PAGE_INDIRECT_Y=(0xf1, '5**')),
    Instruction('sta', ZERO_PAGE_INDIRECT=(0x92, '5')),
    Instruction('stz', ABSOLUTE=(0x9c, '4'),
                       ABSOLUTE_X=(0x9e, '5'),
                       ZERO_PAGE=(0x64, '3'),
                       ZERO_PAGE_X=(0x74, '4')),
    Instruction('trb', ABSOLUTE=(0x1c, '6'),
                       ZERO_PAGE=(0x14, '5')),
    Instruction('tsb', ABSOLUTE=(0x0c, '6'),
                       ZERO_PAGE=(0x04, '5'))}

# the Rockwell bit instructions, which the WDC 65C02 has too: rmb and smb reset and set a bit in zero page, and
# bbr and bbs branch if a bit in zero page is reset or set. The bit number is in the mnemonic, and in the high
# nibble of the opcode. bbr and bbs take 5 cycles, and like other branches 1 more if taken, and 1 more to another page
_rockwellInstructionSet = {
    Instruction('bbr0', ZERO_PAGE_RELATIVE=(0x0f, '5**')),
    Instruction('bbr1', ZERO_PAGE_RELATIVE=(0x1f, '5**')),
    Instruction('bbr2', ZERO_PAGE_RELATIVE=(0x2f, '5**')),
    Instruction('bbr3', ZERO_PAGE_RELATIVE=(0x3f, '5**')),
    Instruction('bbr4', ZERO_PAGE_RELATIVE=(0x4f, '5**')),
    Instruction('bbr5', ZERO_PAGE_RELATIVE=(0x5f, '5**')),
    Instruction('bbr6', ZERO_PAGE_RELATIVE=(0x6f, '5**')),
    Instruction('bbr7', ZERO_PAGE_RELATIVE=(0x7f, '5**')),
    Instruction('bbs0', ZERO_PAGE_RELATIVE=(0x8f, '5**')),
    Instruction('bbs1', ZERO_PAGE_RELATIVE=(0x9f, '5**')),
    Instruction('bbs2', ZERO_PAGE_RELATIVE=(0xaf, '5**')),
    Instruction('bbs3', ZERO_PAGE_RELATIVE=(0xbf, '5**')),
    Instruction('bbs4', ZERO_PAGE_RELATIVE=(0xcf, '5**')),
    Instruction('bbs5', ZERO_PAGE_RELATIVE=(0xdf, '5**')),
    Instruction('bbs6', ZERO_PAGE_RELATIVE=(0xef, '5**')),
    Instruction('bbs7', ZERO_PAGE_RELATIVE=(0xff, '5**')),
    Instruction('rmb0', ZERO_PAGE=(0x07, '5')),
    Instruction('rmb1', ZERO_PAGE=(0x17, '5')),
    Instruction('rmb2', ZERO_PAGE=(0x27, '5')),
    Instruction('rmb3', ZERO_PAGE=(0x37, '5')),
    Instruction('rmb4', ZERO_PAGE=(0x47, '5')),
    Instruction('rmb5', ZERO_PAGE=(0x57, '5')),
    Instruction('rmb6', ZERO_PAGE=(0x67, '5')),
    Instruction('rmb7', ZERO_PAGE=(0x77, '5')),
    Instruction('smb0', ZERO_PAGE=(0x87, '5')),
    Instruction('smb1', ZERO_PAGE=(0x97, '5')),
    Instruction('smb2', ZERO_PAGE=(0xa7, '5')),
    Instruction('smb3', ZERO_PAGE=(0xb7, '5')),
    Instruction('smb4', ZERO_PAGE=(0xc7, '5')),
    Instruction('smb5', ZERO_PAGE=(0xd7, '5')),
    Instruction('smb6', ZERO_PAGE=(0xe7, '5')),
    Instruction('smb7', ZERO_PAGE=(0xf7, '5'))}

# the instructions only the WDC 65C02 has: wai waits for an interrupt, and stp stops the cpu until a reset
_wdcInstructionSet = {
    Instruction('stp', IMPLIED=(0xdb, '3')),
    Instruction('wai', IMPLIED=(0xcb, '3'))}


class CPU:
    """A CPU of the 6502 family: its instructions, looked up by mnemonic or by opcode."""

    def __init__(self, name: str, *instructionSets: set[Instruction]):
        """The instructions of the sets. An instruction in a later set adds its address modes to the one
        with the same mnemonic, e.g. the 65C02's lda ($12) to the 6502's lda. A mode it repeats, with the same
        opcode, gets the later set's cycles. Raises ValueError if an instruction has two opcodes for the same
        mode, or two instructions have the same opcode."""
        self.name = name
        modes: dict[str, dict[AddressMode, int]] = {} # mnemonic: {address mode: opcode}
        cycles: dict[str, dict[AddressMode, str]] = {} # mnemonic: {address mode: cycles}
        for instructionSet in instructionSets:
            for instruction in instructionSet:
                opcodes = modes.setdefault(instruction.mnemonic, {})
                for mode, opcode in instruction.opcodes.items():
                    if opcodes.get(mode, opcode) != opcode:
                        raise ValueError(f'{name}: {instruction.mnemonic} has two opcodes for {mode.name}')
                    opcodes[mode] = opcode
                    cycles.setdefault(instruction.mnemonic, {})[mode] = instruction.cycles[mode]
        instructions = [Instruction(mnemonic) for mnemonic in modes]
        for instruction in instructions:
            instruction.opcodes = modes[instruction.mnemonic]
            instruction.cycles = cycles[instruction.mnemonic]
        self._mnemonicMap = {instruction.mnemonic: instruction for instruction in instructions}
        self._opcodeMap: dict[int, tuple[Instruction, AddressMode]] = {}
        for instruction in instructions:
            for mode, opcode in instruction.opcodes.items():
                if opcode in self._opcodeMap:
                    raise ValueError(f'{name}: opcode ${opcode:02x} is used by both {self._opcodeMap[opcode][0].mnemonic} and {instruction.mnemonic}')
                self._opcodeMap[opcode] = (instruction, mode)

    def __repr__(self) -> str:
        """The cpu by its name, e.g. CPU('6502'), as in messages."""
        return f'CPU({self.name!r})'

    def instructionWithMnemonic(self, mnemonic: str) -> Instruction | None:
        """Return the instruction for a lower case mnemonic, e.g. 'lda', or None."""
        return self._mnemonicMap.get(mnemonic)

    def instructionForOpcode(self, opcode: int) -> tuple[Instruction, AddressMode] | None:
        """Return the (instruction, address mode) of an opcode, e.g. 0xa9 is lda immediate, or None."""
        return self._opcodeMap.get(opcode)

    def isMnemonic(self, mnemonic: str) -> bool:
        """Check if a string is an instruction mnemonic."""
        return mnemonic in self._mnemonicMap


# the 6502: the documented instructions, and the stable illegal ones
CPU_6502 = CPU('6502', _documentedInstructionSet, _illegalInstructionSet)

# the 65C02: the documented instructions, and the CMOS ones
CPU_65C02 = CPU('65C02', _documentedInstructionSet, _cmosInstructionSet)

# the Rockwell 65C02: the 65C02, and the Rockwell bit instructions
CPU_R65C02 = CPU('R65C02', _documentedInstructionSet, _cmosInstructionSet, _rockwellInstructionSet)

# the WDC 65C02: the Rockwell 65C02, and wai and stp
CPU_W65C02 = CPU('W65C02', _documentedInstructionSet, _cmosInstructionSet, _rockwellInstructionSet, _wdcInstructionSet)


def isMnemonic(mnemonic: str) -> bool:
    """Check if a string is an instruction mnemonic of any of the cpus, e.g. for the lexer, which runs before a cpu is chosen."""
    return any(cpu.isMnemonic(mnemonic) for cpu in (CPU_6502, CPU_65C02, CPU_R65C02, CPU_W65C02))
