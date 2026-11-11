#! /usr/bin/env python3
"""Tests of the 6502 instruction set."""

import unittest

from ..cpu import (
    AddressMode,
    CPU,
    CPU_6502,
    CPU_65C02,
    CPU_R65C02,
    CPU_W65C02,
    Instruction,
    _cmosInstructionSet,
    _documentedInstructionSet,
    _illegalInstructionSet,
    _rockwellInstructionSet,
    _wdcInstructionSet,
    isMnemonic,
)


class TestCpu(unittest.TestCase):
    """Tests of the instruction set table and lookups.

    The opcodes themselves are tested by testOpcodes and testIllegalOpcodes in
    test_instructions.py, which assemble every instruction in every address mode.
    """

    def testDocumentedInstructionSet(self):
        """The table has all instructions, and they can be looked up by mnemonic."""
        self.assertEqual(len(_documentedInstructionSet), 56) # the documented 6502 instructions

        i = CPU_6502.instructionWithMnemonic('lda')
        self.assertEqual(i.mnemonic, 'lda')

        i = CPU_6502.instructionWithMnemonic('xxx')
        self.assertEqual(i, None)

    def testInstructionForOpcode(self):
        """Each opcode gives its instruction and address mode, the reverse of the instruction set table."""
        instruction, mode = CPU_6502.instructionForOpcode(0xa9)
        self.assertEqual((instruction.mnemonic, mode), ('lda', AddressMode.IMMEDIATE))
        instruction, mode = CPU_6502.instructionForOpcode(0x60)
        self.assertEqual((instruction.mnemonic, mode), ('rts', AddressMode.IMPLIED))
        self.assertEqual(CPU_6502.instructionForOpcode(0x02), None) # jam, freezes the cpu

    def _opcodeCount(self) -> int:
        """The number of opcodes in use."""
        return sum(CPU_6502.instructionForOpcode(opcode) is not None for opcode in range(256))

    def testIllegalInstructionSets(self):
        """The number of stable illegal instructions."""
        self.assertEqual(len(_illegalInstructionSet), 13)

    def testCmosInstructionSet(self):
        """The 65C02 adds 27 opcodes, on opcodes the 6502 doesn't use. The 6502 modes it repeats, to change their
        cycles, keep their opcodes."""
        cmos = {(i.mnemonic, mode): opcode for i in _cmosInstructionSet for mode, opcode in i.opcodes.items()}
        documented = {(i.mnemonic, mode): opcode for i in _documentedInstructionSet for mode, opcode in i.opcodes.items()}
        added = {key: opcode for key, opcode in cmos.items() if key not in documented}
        self.assertEqual(len(added), 27)
        self.assertEqual(set(added.values()) & set(documented.values()), set())
        self.assertEqual({key: cmos[key] for key in cmos if key in documented}, {key: documented[key] for key in cmos if key in documented})

    def testRockwellInstructionSet(self):
        """Rockwell adds 32 bit instructions: rmb and smb reset and set a bit in zero page, and bbr and bbs branch on one.
        The bit number is in the high nibble of the opcode, and the opcodes are ones the 65C02 doesn't use."""
        self.assertEqual(len(_rockwellInstructionSet), 32)
        cpu = CPU('test', _documentedInstructionSet, _cmosInstructionSet, _rockwellInstructionSet) # raises ValueError on a clash
        for bit in range(8):
            with self.subTest(bit=bit):
                self.assertEqual(cpu.instructionWithMnemonic(f'rmb{bit}').opcodes, {AddressMode.ZERO_PAGE: 0x07 + bit * 0x10})
                self.assertEqual(cpu.instructionWithMnemonic(f'smb{bit}').opcodes, {AddressMode.ZERO_PAGE: 0x87 + bit * 0x10})
                self.assertEqual(cpu.instructionWithMnemonic(f'bbr{bit}').opcodes, {AddressMode.ZERO_PAGE_RELATIVE: 0x0f + bit * 0x10})
                self.assertEqual(cpu.instructionWithMnemonic(f'bbs{bit}').opcodes, {AddressMode.ZERO_PAGE_RELATIVE: 0x8f + bit * 0x10})
        self.assertEqual(cpu.instructionWithMnemonic('rmb0').cycles[AddressMode.ZERO_PAGE], '5')
        self.assertEqual(cpu.instructionWithMnemonic('bbr0').cycles[AddressMode.ZERO_PAGE_RELATIVE], '5**') # like a branch

    def testWdcInstructionSet(self):
        """WDC adds wai, which waits for an interrupt, and stp, which stops the cpu until a reset."""
        self.assertEqual({(i.mnemonic, mode, opcode) for i in _wdcInstructionSet for mode, opcode in i.opcodes.items()},
                         {('wai', AddressMode.IMPLIED, 0xcb), ('stp', AddressMode.IMPLIED, 0xdb)})

    def testIllegalInstructions(self):
        """The stable illegal instructions are instructions, but not the illegal nops, usbc, or the unstable ones."""
        self.assertEqual(self._opcodeCount(), 208)
        self.assertEqual(CPU_6502.instructionForOpcode(0xa7), (CPU_6502.instructionWithMnemonic('lax'), AddressMode.ZERO_PAGE))
        self.assertEqual(CPU_6502.instructionForOpcode(0x04), None) # an illegal nop
        self.assertEqual(CPU_6502.instructionForOpcode(0xeb), None) # usbc, the same as sbc #
        self.assertEqual(CPU_6502.isMnemonic('sha'), False)         # unstable

    def testCPU6502(self):
        """The 6502 is the documented instructions and the stable illegal ones, looked up by mnemonic and by opcode."""
        self.assertEqual(CPU_6502.name, '6502')
        self.assertEqual(sum(CPU_6502.instructionForOpcode(opcode) is not None for opcode in range(256)), 208)
        lax = CPU_6502.instructionWithMnemonic('lax')
        self.assertEqual(lax.opcodes[AddressMode.ZERO_PAGE], 0xa7)
        self.assertEqual(CPU_6502.instructionForOpcode(0xa7), (lax, AddressMode.ZERO_PAGE))
        self.assertEqual((CPU_6502.isMnemonic('lda'), CPU_6502.isMnemonic('bra')), (True, False))
        self.assertEqual((CPU_6502.instructionWithMnemonic('bra'), CPU_6502.instructionForOpcode(0x02)), (None, None))

    def testCPUMergesByMnemonic(self):
        """An instruction in a later set adds its modes to the one with the same mnemonic, as the 65C02's do."""
        cpu = CPU_65C02
        self.assertEqual(cpu.name, '65C02')
        lda = cpu.instructionWithMnemonic('lda')
        self.assertEqual(lda.opcodes[AddressMode.IMMEDIATE], 0xa9)           # from the 6502
        self.assertEqual(lda.opcodes[AddressMode.ZERO_PAGE_INDIRECT], 0xb2)  # from the CMOS instructions
        self.assertEqual(cpu.instructionForOpcode(0xb2), (lda, AddressMode.ZERO_PAGE_INDIRECT))
        self.assertEqual(sum(cpu.instructionForOpcode(opcode) is not None for opcode in range(256)), 151 + 27)
        self.assertEqual((cpu.isMnemonic('bra'), cpu.isMnemonic('lax')), (True, False))

    def testCPUR65C02(self):
        """The Rockwell 65C02 is the 65C02 and the Rockwell bit instructions."""
        self.assertEqual(CPU_R65C02.name, 'R65C02')
        self.assertEqual(sum(CPU_R65C02.instructionForOpcode(opcode) is not None for opcode in range(256)), 151 + 27 + 32)
        self.assertEqual(CPU_R65C02.instructionForOpcode(0x3f), (CPU_R65C02.instructionWithMnemonic('bbr3'), AddressMode.ZERO_PAGE_RELATIVE))
        self.assertEqual((CPU_R65C02.isMnemonic('bra'), CPU_R65C02.isMnemonic('smb7'), CPU_R65C02.isMnemonic('lax')), (True, True, False))
        self.assertEqual(CPU_65C02.isMnemonic('smb7'), False)

    def testCPUW65C02(self):
        """The WDC 65C02 is the Rockwell 65C02, and wai and stp."""
        self.assertEqual(CPU_W65C02.name, 'W65C02')
        self.assertEqual(sum(CPU_W65C02.instructionForOpcode(opcode) is not None for opcode in range(256)), 151 + 27 + 32 + 2)
        self.assertEqual(CPU_W65C02.instructionForOpcode(0xcb), (CPU_W65C02.instructionWithMnemonic('wai'), AddressMode.IMPLIED))
        self.assertEqual((CPU_W65C02.isMnemonic('bbr0'), CPU_W65C02.isMnemonic('stp'), CPU_R65C02.isMnemonic('stp')), (True, True, False))

    def testCPUClashes(self):
        """Two instructions with the same opcode, or two opcodes for the same mode of an instruction, are an error.
        A later set may repeat a mode with the same opcode."""
        for first, second in [(Instruction('aaa', IMPLIED=(0x01, '2')), Instruction('bbb', IMPLIED=(0x01, '2'))),
                              (Instruction('lda', IMMEDIATE=(0xa9, '2')), Instruction('lda', IMMEDIATE=(0x42, '2')))]:
            with self.subTest(second=second.mnemonic):
                self.assertRaises(ValueError, CPU, 'test', {first}, {second})
        cpu = CPU('test', {Instruction('lda', IMMEDIATE=(0xa9, '2'))}, {Instruction('lda', IMMEDIATE=(0xa9, '3'))})
        self.assertEqual(cpu.instructionForOpcode(0xa9)[1], AddressMode.IMMEDIATE)
        self.assertEqual(cpu.instructionWithMnemonic('lda').cycles[AddressMode.IMMEDIATE], '3') # the later set's cycles

    def testCycles(self):
        """Every mode has its cycles, a '*' for each cycle that may be added, e.g. when a page is crossed or a
        branch is taken. The 65C02 changes some of them."""
        for cpu in [CPU_6502, CPU_65C02]:
            for opcode in range(256):
                if found := cpu.instructionForOpcode(opcode):
                    with self.subTest(cpu=cpu.name, opcode=opcode):
                        self.assertRegex(found[0].cycles[found[1]], r'^[2-8]\*{0,2}$')
        for mnemonic, mode, cycles6502, cycles65C02 in [
            ('lda', AddressMode.ABSOLUTE_X,        '4*',  '4*'),   # a page crossed
            ('bne', AddressMode.RELATIVE,          '2**', '2**'),  # taken, and to another page
            ('sta', AddressMode.ABSOLUTE_X,        '5',   '5'),
            ('dec', AddressMode.ABSOLUTE,          '6',   '6'),    # py65 has 3
            ('jmp', AddressMode.ABSOLUTE_INDIRECT, '5',   '6'),    # the 65C02 fixes the page boundary bug
            ('asl', AddressMode.ABSOLUTE_X,        '7',   '6*'),   # faster on the 65C02, unless a page is crossed
            ('adc', AddressMode.IMMEDIATE,         '2',   '2*'),   # decimal mode on the 65C02
            ('adc', AddressMode.ABSOLUTE_Y,        '4*',  '4**'),
            ('lax', AddressMode.ZERO_PAGE_INDIRECT_Y, '5*', None), # illegal, 6502 only
            ('bra', AddressMode.RELATIVE,          None,  '3*'),   # 65C02 only
        ]:
            for cpu, expected in [(CPU_6502, cycles6502), (CPU_65C02, cycles65C02)]:
                with self.subTest(cpu=cpu.name, mnemonic=mnemonic, mode=mode.name):
                    instruction = cpu.instructionWithMnemonic(mnemonic)
                    self.assertEqual(instruction.cycles[mode] if instruction else None, expected)

    def testIsMnemonic(self):
        """Only instruction mnemonics are recognized, in lowercase."""
        self.assertEqual(CPU_6502.isMnemonic(''), False)
        self.assertEqual(CPU_6502.isMnemonic('xxx'), False)
        self.assertEqual(CPU_6502.isMnemonic('lda'), True)
        self.assertEqual(CPU_6502.isMnemonic('sta'), True)
        self.assertEqual(CPU_6502.isMnemonic('nop'), True)
        self.assertEqual(CPU_6502.isMnemonic('LDA'), False)

    def testIsMnemonicOfAnyCPU(self):
        """A mnemonic of any of the cpus, the 6502 with its illegal instructions, the 65C02, the Rockwell or the WDC 65C02."""
        for mnemonic, expected in [('lda', True), ('lax', True), ('stz', True), ('bra', True), ('rmb0', True), ('bbs7', True),
                                   ('wai', True), ('stp', True), ('xxx', False), ('LDA', False)]:
            with self.subTest(mnemonic=mnemonic):
                self.assertEqual(isMnemonic(mnemonic), expected)

    def testSize(self):
        """The size of an instruction, by address mode: the opcode, and a byte or word operand."""
        self.assertEqual(AddressMode.IMPLIED.size, 1)                # rts
        self.assertEqual(AddressMode.ACCUMULATOR.size, 1)            # asl
        self.assertEqual(AddressMode.IMMEDIATE.size, 2)              # lda #$01
        self.assertEqual(AddressMode.RELATIVE.size, 2)               # bne label
        self.assertEqual(AddressMode.ZERO_PAGE_INDIRECT_Y.size, 2)   # lda ($10),y
        self.assertEqual(AddressMode.ZERO_PAGE_INDIRECT.size, 2)     # lda ($10), on the 65C02
        self.assertEqual(AddressMode.ABSOLUTE_X.size, 3)             # lda $1234,x
        self.assertEqual(AddressMode.ABSOLUTE_INDIRECT.size, 3)      # jmp ($1234)
        self.assertEqual(AddressMode.ABSOLUTE_INDIRECT_X.size, 3)    # jmp ($1234,x), on the 65C02
        self.assertEqual(AddressMode.ZERO_PAGE_RELATIVE.size, 3)     # bbr0 $10,label, on the Rockwell and WDC 65C02

    def testSyntax(self):
        """The operand of each address mode, written in assembler syntax."""
        for mode, expected in [(AddressMode.IMPLIED, ''),        (AddressMode.ACCUMULATOR, ''),
                               (AddressMode.IMMEDIATE, '#$10'),  (AddressMode.RELATIVE, '$10'),
                               (AddressMode.ZERO_PAGE, '$10'),    (AddressMode.ZERO_PAGE_X, '$10,x'),
                               (AddressMode.ZERO_PAGE_Y, '$10,y'), (AddressMode.ZERO_PAGE_INDIRECT_X, '($10,x)'),
                               (AddressMode.ZERO_PAGE_INDIRECT_Y, '($10),y'), (AddressMode.ABSOLUTE, '$10'),
                               (AddressMode.ABSOLUTE_X, '$10,x'), (AddressMode.ABSOLUTE_Y, '$10,y'),
                               (AddressMode.ABSOLUTE_INDIRECT, '($10)'), (AddressMode.ZERO_PAGE_INDIRECT, '($10)'),
                               (AddressMode.ABSOLUTE_INDIRECT_X, '($10,x)')]:
            with self.subTest(mode=mode):
                self.assertEqual(mode.syntax('$10'), expected)
        self.assertEqual(AddressMode.ZERO_PAGE_RELATIVE.syntax('$10', '$1234'), '$10,$1234') # a zero page address, and a branch

    def testZeroPageMode(self):
        """The zero page mode that is chosen instead of an absolute mode, for addresses below $100."""
        self.assertEqual(AddressMode.ABSOLUTE.zeroPageMode, AddressMode.ZERO_PAGE)
        self.assertEqual(AddressMode.ABSOLUTE_X.zeroPageMode, AddressMode.ZERO_PAGE_X)
        self.assertEqual(AddressMode.ABSOLUTE_Y.zeroPageMode, AddressMode.ZERO_PAGE_Y)
        self.assertEqual(AddressMode.ABSOLUTE_INDIRECT.zeroPageMode, None) # always a word
        self.assertEqual(AddressMode.ABSOLUTE_INDIRECT_X.zeroPageMode, None) # always a word, on the 65C02
        self.assertEqual(AddressMode.ZERO_PAGE.zeroPageMode, None)

    def testUnknownAddressMode(self):
        """A misspelled address mode in the table is an error when the module is loaded."""
        self.assertRaises(KeyError, Instruction, 'xxx', zeroPagee=(0x00, '2'))


if __name__ == '__main__':
    unittest.main()
