"""BASIC 2.0 on the C64: the tokens and generators, the start address of a program, and the address of the ROM."""

from nopa.basic import BASIC_2 as _BASIC

globals().update(_BASIC.symbols()) # the BASIC_TOKEN_ symbols, and the generators basicStart(), basicLine(), basicSys() and basicEnd()

BASIC_START_ADDRESS = 0x0801

BASIC_ROM           = 0xa000
