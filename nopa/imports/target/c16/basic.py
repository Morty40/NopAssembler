"""BASIC 3.5 on the C16: the tokens, the generators, and the start address of a program."""

from nopa.basic import BASIC_3_5 as _BASIC

globals().update(_BASIC.symbols(SOURCE_FOLDER)) # the BASIC_TOKEN_ symbols, and basic, with the generators, such as basic.line()

BASIC_START_ADDRESS = 0x1001
