"""The memory layout: the bank registers and the banked RAM and ROM windows, the ROM banks, and the free zero page."""

RAM_BANK   = 0x00   # the RAM bank in the BANKED_RAM window, 0-255
ROM_BANK   = 0x01   # the ROM bank in the BANKED_ROM window: 0-31 ROM, 32-255 cartridge RAM or ROM

BANKED_RAM = 0xa000 # 8K, to $bfff
BANKED_ROM = 0xc000 # 16K, to $ffff

# the ROM banks, which may still change
ROM_BANK_KERNAL  = 0
ROM_BANK_KEYBD   = 1  # keyboard layouts
ROM_BANK_CBDOS   = 2  # CMDR-DOS, for the SD card
ROM_BANK_FAT32   = 3
ROM_BANK_BASIC   = 4
ROM_BANK_MONITOR = 5
ROM_BANK_CHARSET = 6  # PETSCII and ISO character sets
ROM_BANK_DIAG    = 7  # memory diagnostic
ROM_BANK_GRAPH   = 8  # KERNAL graphics and fonts
ROM_BANK_DEMO    = 9
ROM_BANK_AUDIO   = 10
ROM_BANK_UTIL    = 11 # system configuration
ROM_BANK_BANNEX  = 12 # BASIC annex
ROM_BANK_X16EDIT = 13 # the text editor, in banks 13 and 14
ROM_BANK_BASLOAD = 15

# the zero page free for programs. $02-$21 are the KERNAL registers r0 to r15, and $80-$ff are used by the KERNAL and BASIC
ZERO_PAGE_USER     = 0x22
ZERO_PAGE_USER_END = 0x7f
