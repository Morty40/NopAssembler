"""The screen and color RAM, which depend on the memory expansion."""

# without a memory expansion, or with 3K
SCREEN_RAM = 0x1e00
COLOR_RAM  = 0x9600

# with 8K or more
SCREEN_RAM_EXPANDED = 0x1000
COLOR_RAM_EXPANDED  = 0x9400
