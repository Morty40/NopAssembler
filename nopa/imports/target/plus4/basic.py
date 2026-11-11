"""BASIC 3.5 on the Plus/4: the tokens and generators, the start address of a program, and the address of the ROM."""

from nopa.basic import BASIC_3_5 as _BASIC

globals().update(_BASIC.symbols()) # the BASIC_TOKEN_ symbols, and the generators basicStart(), basicLine(), basicSys() and basicEnd()

BASIC_START_ADDRESS = 0x1001

BASIC_ROM           = 0x8000
