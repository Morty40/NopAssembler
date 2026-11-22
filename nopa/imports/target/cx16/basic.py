"""BASIC 2.0 on the Commander X16: the tokens, the generators, and the start address of a program.

The X16's own keywords, such as VPOKE, are not tokens, so @basic.line writes them as text.
"""

from nopa.basic import BASIC_2 as _BASIC

globals().update(_BASIC.symbols(SOURCE_FOLDER)) # the BASIC_TOKEN_ symbols, and basic, with the generators, such as basic.line()

BASIC_START_ADDRESS = 0x0801
