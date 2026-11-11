#! /usr/bin/env python3
"""Tests of the 6502 instructions."""

import unittest

from .. import lexer
from ..context import Context
from ..cpu import CPU, CPU_6502, CPU_65C02, CPU_R65C02
from ..instructions import assemble


class TestInstructions(unittest.TestCase):
    """Tests of choosing the address mode, and the bytes stored."""

    def _assemble(self, line: str, cpu: CPU = CPU_6502):
        """Assemble one instruction at $1000 for the cpu, and return the bytes and the context."""
        context = Context({'_': 0x1000})
        context.cpu = cpu
        assemble(lexer.tokenize(line)[:-1], context)
        return [context.memory[address] for address in sorted(context.memory)], context

    def testAddressModes(self):
        """Each address mode, chosen from the operand syntax."""
        for line, expected in [
            ('rts',         [0x60]),             # implied
            ('asl',         [0x0a]),             # accumulator
            ('lda #1',      [0xa9, 0x01]),       # immediate
            ('lda ($10,x)', [0xa1, 0x10]),       # indexed indirect
            ('lda ($10),y', [0xb1, 0x10]),       # indirect indexed
            ('jmp ($1234)', [0x6c, 0x34, 0x12]), # indirect
            ('bne $1000',   [0xd0, 0xfe]),       # relative, to itself
            ('lda $10,x',   [0xb5, 0x10]),       # zero page,x
            ('lda $1234,x', [0xbd, 0x34, 0x12]), # absolute,x
            ('ldx $10,y',   [0xb6, 0x10]),       # zero page,y
            ('lda $10,y',   [0xb9, 0x10, 0x00]), # absolute,y, as lda has no zero page,y
            ('lda $10',     [0xa5, 0x10]),       # zero page
            ('lda $1234',   [0xad, 0x34, 0x12]), # absolute
            ('jmp $10',     [0x4c, 0x10, 0x00]), # absolute, as jmp has no zero page
        ]:
            with self.subTest(line=line):
                data, context = self._assemble(line)
                self.assertEqual(data, expected)
                self.assertEqual(context.errors + context.warnings, [])

    def testIndirect65C02(self):
        """The 65C02's lda ($12) and jmp ($1234,x), chosen by the instruction's modes, next to the 6502's ones."""
        for line, expected, errors in [
            ('lda ($12)',     [0xb2, 0x12],       []),
            ('lda ($12,x)',   [0xa1, 0x12],       []),
            ('lda ($12),y',   [0xb1, 0x12],       []),
            ('jmp ($1234,x)', [0x7c, 0x34, 0x12], []),
            ('jmp ($1234)',   [0x6c, 0x34, 0x12], []),
            ('lda ($1234)',   [0xb2, 0x34],       ['error: Byte value out of range: 4660']), # (zp) is a zero page address
        ]:
            with self.subTest(line=line):
                data, context = self._assemble(line, CPU_65C02)
                self.assertEqual(data, expected)
                self.assertEqual(context.errors + context.warnings, errors)

    def testIndirectPageBoundary(self):
        """jmp ($xxff) is assembled, with a warning on the 6502, which does not cross the page, but not on the 65C02."""
        for cpu, warnings in [(CPU_6502, ['warning: Indirect address located on page boundary: $10ff']), (CPU_65C02, [])]:
            with self.subTest(cpu=cpu.name):
                data, context = self._assemble('jmp ($10ff)', cpu)
                self.assertEqual(data, [0x6c, 0xff, 0x10])
                self.assertEqual(context.warnings, warnings)

    def testUnknownAddressMode(self):
        """An operand the instruction has no address mode for is an error, and nothing is stored."""
        for line, operand in [('stx $1234,y', '0x1234,y'), # no absolute,y
                              ('sty $1234,x', '0x1234,x'), # no absolute,x
                              ('lda', '')]:                # no implied
            with self.subTest(line=line):
                data, context = self._assemble(line)
                self.assertEqual(data, [])
                self.assertEqual(context.errors, [f'error: Unknown instruction or address mode: {line.split()[0]} {operand}'])

    def _assertOpcodes(self, table: list):
        """Each row is an operand, its bytes, and the opcode of each instruction with that operand."""
        for operand, operandBytes, opcodes in table:
            for mnemonic, opcode in opcodes.items():
                line = f'{mnemonic} {operand}'
                with self.subTest(line=line):
                    data, context = self._assemble(line)
                    self.assertEqual(data, [opcode] + operandBytes)
                    self.assertEqual(context.errors + context.warnings, [])

    def testOpcodes(self):
        """The opcode of every documented instruction, in every address mode."""
        self._assertOpcodes([
            ('',          [],
             {'brk': 0x00, 'clc': 0x18, 'cld': 0xd8, 'cli': 0x58, 'clv': 0xb8, 'dex': 0xca, 'dey': 0x88,
              'inx': 0xe8, 'iny': 0xc8, 'nop': 0xea, 'pha': 0x48, 'php': 0x08, 'pla': 0x68, 'plp': 0x28,
              'rti': 0x40, 'rts': 0x60, 'sec': 0x38, 'sed': 0xf8, 'sei': 0x78, 'tax': 0xaa, 'tay': 0xa8,
              'tsx': 0xba, 'txa': 0x8a, 'txs': 0x9a, 'tya': 0x98, 'asl': 0x0a, 'lsr': 0x4a, 'rol': 0x2a,
              'ror': 0x6a}),
            ('#$12',      [0x12],
             {'adc': 0x69, 'and': 0x29, 'cmp': 0xc9, 'cpx': 0xe0, 'cpy': 0xc0, 'eor': 0x49, 'lda': 0xa9,
              'ldx': 0xa2, 'ldy': 0xa0, 'ora': 0x09, 'sbc': 0xe9}),
            ('$02',       [0x02],
             {'adc': 0x65, 'and': 0x25, 'asl': 0x06, 'bit': 0x24, 'cmp': 0xc5, 'cpx': 0xe4, 'cpy': 0xc4,
              'dec': 0xc6, 'eor': 0x45, 'inc': 0xe6, 'lda': 0xa5, 'ldx': 0xa6, 'ldy': 0xa4, 'lsr': 0x46,
              'ora': 0x05, 'rol': 0x26, 'ror': 0x66, 'sbc': 0xe5, 'sta': 0x85, 'stx': 0x86, 'sty': 0x84}),
            ('$02,x',     [0x02],
             {'adc': 0x75, 'and': 0x35, 'asl': 0x16, 'cmp': 0xd5, 'dec': 0xd6, 'eor': 0x55, 'inc': 0xf6,
              'lda': 0xb5, 'ldy': 0xb4, 'lsr': 0x56, 'ora': 0x15, 'rol': 0x36, 'ror': 0x76, 'sbc': 0xf5,
              'sta': 0x95, 'sty': 0x94}),
            ('$02,y',     [0x02],
             {'ldx': 0xb6, 'stx': 0x96}),
            ('$1234',     [0x34, 0x12],
             {'adc': 0x6d, 'and': 0x2d, 'asl': 0x0e, 'bit': 0x2c, 'cmp': 0xcd, 'cpx': 0xec, 'cpy': 0xcc,
              'dec': 0xce, 'eor': 0x4d, 'inc': 0xee, 'jmp': 0x4c, 'jsr': 0x20, 'lda': 0xad, 'ldx': 0xae,
              'ldy': 0xac, 'lsr': 0x4e, 'ora': 0x0d, 'rol': 0x2e, 'ror': 0x6e, 'sbc': 0xed, 'sta': 0x8d,
              'stx': 0x8e, 'sty': 0x8c}),
            ('$1234,x',   [0x34, 0x12],
             {'adc': 0x7d, 'and': 0x3d, 'asl': 0x1e, 'cmp': 0xdd, 'dec': 0xde, 'eor': 0x5d, 'inc': 0xfe,
              'lda': 0xbd, 'ldy': 0xbc, 'lsr': 0x5e, 'ora': 0x1d, 'rol': 0x3e, 'ror': 0x7e, 'sbc': 0xfd,
              'sta': 0x9d}),
            ('$1234,y',   [0x34, 0x12],
             {'adc': 0x79, 'and': 0x39, 'cmp': 0xd9, 'eor': 0x59, 'lda': 0xb9, 'ldx': 0xbe, 'ora': 0x19,
              'sbc': 0xf9, 'sta': 0x99}),
            ('($1234)',   [0x34, 0x12],
             {'jmp': 0x6c}),
            ('($12,x)',   [0x12],
             {'adc': 0x61, 'and': 0x21, 'cmp': 0xc1, 'eor': 0x41, 'lda': 0xa1, 'ora': 0x01, 'sbc': 0xe1,
              'sta': 0x81}),
            ('($12),y',   [0x12],
             {'adc': 0x71, 'and': 0x31, 'cmp': 0xd1, 'eor': 0x51, 'lda': 0xb1, 'ora': 0x11, 'sbc': 0xf1,
              'sta': 0x91}),
            ('$1000',     [0xfe], # a branch to itself
             {'bcc': 0x90, 'bcs': 0xb0, 'beq': 0xf0, 'bmi': 0x30, 'bne': 0xd0, 'bpl': 0x10, 'bvc': 0x50,
              'bvs': 0x70}),
        ])

    def testIllegalOpcodes(self):
        """The opcode of every stable illegal instruction, in every address mode."""
        self._assertOpcodes([
            ('#$12',      [0x12],
             {'alr': 0x4b, 'anc': 0x0b, 'arr': 0x6b, 'sbx': 0xcb}),
            ('$12',       [0x12],
             {'dcp': 0xc7, 'isc': 0xe7, 'lax': 0xa7, 'rla': 0x27, 'rra': 0x67, 'sax': 0x87, 'slo': 0x07,
              'sre': 0x47}),
            ('$12,x',     [0x12],
             {'dcp': 0xd7, 'isc': 0xf7, 'rla': 0x37, 'rra': 0x77, 'slo': 0x17, 'sre': 0x57}),
            ('$1234',     [0x34, 0x12],
             {'dcp': 0xcf, 'isc': 0xef, 'lax': 0xaf, 'rla': 0x2f, 'rra': 0x6f, 'sax': 0x8f, 'slo': 0x0f,
              'sre': 0x4f}),
            ('$1234,x',   [0x34, 0x12],
             {'dcp': 0xdf, 'isc': 0xff, 'rla': 0x3f, 'rra': 0x7f, 'slo': 0x1f, 'sre': 0x5f}),
            ('$1234,y',   [0x34, 0x12],
             {'dcp': 0xdb, 'isc': 0xfb, 'las': 0xbb, 'lax': 0xbf, 'rla': 0x3b, 'rra': 0x7b, 'slo': 0x1b,
              'sre': 0x5b}),
            ('($12,x)',   [0x12],
             {'dcp': 0xc3, 'isc': 0xe3, 'lax': 0xa3, 'rla': 0x23, 'rra': 0x63, 'sax': 0x83, 'slo': 0x03,
              'sre': 0x43}),
            ('($12),y',   [0x12],
             {'dcp': 0xd3, 'isc': 0xf3, 'lax': 0xb3, 'rla': 0x33, 'rra': 0x73, 'slo': 0x13, 'sre': 0x53}),
            ('$12,y',     [0x12],
             {'lax': 0xb7, 'sax': 0x97}),
        ])

    def testBranchRange(self):
        """A branch reaches -128 to +127 bytes, counted from $1002, the address after the branch."""
        for target, expected in [('$1081', [0xd0, 0x7f]), ('$0f82', [0xd0, 0x80])]:
            with self.subTest(target=target):
                data, context = self._assemble(f'bne {target}')
                self.assertEqual(data, expected)
                self.assertEqual(context.errors, [])

    def testZeroPageRelative(self):
        """bbr and bbs: a zero page address, and a branch of -128 to +127 bytes, counted from $1003, the address after it."""
        for line, expected, errors in [
            ('bbr3 $12,$1000',   [0x3f, 0x12, 0xfd], []),               # to itself
            ('bbr3 $12,$1082',   [0x3f, 0x12, 0x7f], []),               # +127
            ('bbr3 $12,$0f83',   [0x3f, 0x12, 0x80], []),               # -128
            ('bbr3 $12,$1083',   [0x3f, 0x12, 0x00], ['error: Branch destination out of range [-128..127]: 128']),
            ('bbr3 $1234,$1000', [0x3f, 0x34, 0xfd], ['error: Byte value out of range: 4660']), # a zero page address
            ('bbr3 $12',         [],                 ['error: Unknown instruction or address mode: bbr3 0x12']),
        ]:
            with self.subTest(line=line):
                data, context = self._assemble(line, CPU_R65C02)
                self.assertEqual(data, expected)
                self.assertEqual(context.errors + context.warnings, errors)

    def testBranchOutOfRange(self):
        """A branch reaches -128 to +127 bytes. One byte more is an error."""
        # one byte beyond +127 and -128, counted from $1002, the address after the branch
        for target, dist in [('$1082', 128), ('$0f81', -129)]:
            context = Context({'_': 0x1000})
            assemble(lexer.tokenize(f'bne {target}')[:-1], context)
            self.assertEqual(context.errors, [f'error: Branch destination out of range [-128..127]: {dist}'])


if __name__ == '__main__':
    unittest.main()
