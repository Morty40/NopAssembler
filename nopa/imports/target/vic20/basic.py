"""BASIC 2.0 on the VIC-20: the tokens and generators, the start address of a program, without a memory expansion, and the address of the ROM."""

from nopa.basic import BASIC_2 as _BASIC

globals().update(_BASIC.symbols()) # the BASIC_TOKEN_ symbols, and the generators basicStart(), basicLine(), basicSys() and basicEnd()

BASIC_START_ADDRESS = 0x1001

BASIC_ROM           = 0xc000
