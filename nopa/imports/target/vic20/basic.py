"""BASIC 2.0 on the VIC-20: the tokens, the generators, and the start address of a program, without a memory expansion."""

from nopa.basic import BASIC_2 as _BASIC

globals().update(_BASIC.symbols()) # the BASIC_TOKEN_ symbols, and the generators basic.start(), basic.line(), basic.sys() and basic.end()

BASIC_START_ADDRESS = 0x1001
