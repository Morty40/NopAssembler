"""BASIC 2.0 on the C64: the tokens, the generators, and the start address of a program."""

from nopa.basic import BASIC_2 as _BASIC

globals().update(_BASIC.symbols()) # the BASIC_TOKEN_ symbols, and the generators basic.start(), basic.line(), basic.sys() and basic.end()

BASIC_START_ADDRESS = 0x0801
