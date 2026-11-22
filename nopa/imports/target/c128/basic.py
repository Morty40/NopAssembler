"""BASIC 7.0 on the C128: the tokens, the generators, and the start address of a program."""

from nopa.basic import BASIC_7 as _BASIC

globals().update(_BASIC.symbols(SOURCE_FOLDER)) # the BASIC_TOKEN_ symbols, and basic, with the generators, such as basic.line()

BASIC_START_ADDRESS = 0x1c01
