"""BASIC 2.0 on the Commander X16: the tokens and generators, the start address of a program, and the address of the ROM.

The X16's own keywords, such as VPOKE, are not tokens, so @basicLine writes them as text.
"""

from nopa.basic import BASIC_2 as _BASIC

globals().update(_BASIC.symbols()) # the BASIC_TOKEN_ symbols, and the generators basicStart(), basicLine(), basicSys() and basicEnd()

BASIC_START_ADDRESS = 0x0801

BASIC_ROM           = 0xc000 # in ROM bank 4, ROM_BANK_BASIC
