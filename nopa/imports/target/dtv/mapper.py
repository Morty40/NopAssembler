"""The memory mapper, which chooses where the KERNAL and BASIC come from. Only with the VIC's extended registers on, see VIC_EXTENDED."""

MAPPER_KERNAL = 0xd100 # bits 4-0: the 64K segment of the KERNAL, at $e000-$ffff of the segment, bits 7-6: MAPPER_RAM or MAPPER_FLASH
MAPPER_BASIC  = 0xd101 # the same for BASIC, at $a000-$bfff of the segment

MAPPER_FLASH = 0x00 # the default, segment 0 of the flash
MAPPER_RAM   = 0x40
