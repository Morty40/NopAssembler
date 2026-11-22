"""BASIC 7.0 on the C128: the tokens, the generators, and the start address of a program."""

from nopa.basic import BASIC_7 as _BASIC

globals().update(_BASIC.symbols()) # the BASIC_TOKEN_ symbols, and the generators basic.start(), basic.line(), basic.sys() and basic.end()

BASIC_START_ADDRESS = 0x1c01
