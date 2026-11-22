"""The flash memory, an Atmel chip with the ROMs and programs. The cpu reads and writes it in a bank with CPU_ACCESS_FLASH.

A command is $aa written to FLASH_COMMAND_ADDRESS1, $55 to FLASH_COMMAND_ADDRESS2, then the command to FLASH_COMMAND_ADDRESS1.
"""

FLASH_SIZE = 0x200000 # 2M, in 64K sectors, and the last 64K in 8K sectors

FLASH_COMMAND_ADDRESS1 = 0xaaa
FLASH_COMMAND_ADDRESS2 = 0x554
FLASH_UNLOCK1          = 0xaa
FLASH_UNLOCK2          = 0x55

FLASH_COMMAND_PROGRAM    = 0xa0 # then the byte to its address: bits can only be cleared
FLASH_COMMAND_ERASE      = 0x80 # then the unlock again, and FLASH_ERASE_SECTOR to the sector or FLASH_ERASE_CHIP
FLASH_COMMAND_PRODUCT_ID = 0x90 # the manufacturer, $1f, at 0, and the device, $c2, at 2
FLASH_COMMAND_EXIT       = 0xf0 # back to reading, after FLASH_COMMAND_PRODUCT_ID

FLASH_ERASE_SECTOR = 0x30 # sets the bytes of the sector to $ff
FLASH_ERASE_CHIP   = 0x10
