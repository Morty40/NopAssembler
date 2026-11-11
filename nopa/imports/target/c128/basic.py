"""BASIC 7.0 on the C128: the tokens and generators, the start address of a program, and the address of the ROM."""

from nopa.basic import BASIC_7 as _BASIC

globals().update(_BASIC.symbols()) # the BASIC_TOKEN_ symbols, and the generators basicStart(), basicLine(), basicSys() and basicEnd()

BASIC_START_ADDRESS = 0x1c01

BASIC_ROM           = 0x4000
