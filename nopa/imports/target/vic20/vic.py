"""The VIC chip, the 6560 (NTSC) and the 6561 (PAL): its registers and colors."""

VIC_COLOR_BLACK        =  0
VIC_COLOR_WHITE        =  1
VIC_COLOR_RED          =  2
VIC_COLOR_CYAN         =  3
VIC_COLOR_PURPLE       =  4
VIC_COLOR_GREEN        =  5
VIC_COLOR_BLUE         =  6
VIC_COLOR_YELLOW       =  7

# only for the background and auxiliary colors
VIC_COLOR_ORANGE       =  8
VIC_COLOR_LIGHT_ORANGE =  9
VIC_COLOR_LIGHT_RED    = 10
VIC_COLOR_LIGHT_CYAN   = 11
VIC_COLOR_LIGHT_PURPLE = 12
VIC_COLOR_LIGHT_GREEN  = 13
VIC_COLOR_LIGHT_BLUE   = 14
VIC_COLOR_LIGHT_YELLOW = 15

VIC_ORIGIN_X                = 0x9000 # bit 7: interlace, bits 6-0: horizontal origin
VIC_ORIGIN_Y                = 0x9001
VIC_COLUMNS                 = 0x9002 # bit 7: bit 9 of the video address, bits 6-0: columns
VIC_ROWS                    = 0x9003 # bit 7: bit 0 of the raster line, bits 6-1: rows, bit 0: characters 8x16 instead of 8x8
VIC_RASTER_COUNTER          = 0x9004 # bits 8-1 of the raster line
VIC_MEMORY_POINTERS         = 0x9005 # bits 7-4: bits 13-10 of the video address, bits 3-0: bits 13-10 of the character address
VIC_LIGHT_PEN_X             = 0x9006
VIC_LIGHT_PEN_Y             = 0x9007
VIC_PADDLE_X                = 0x9008
VIC_PADDLE_Y                = 0x9009
VIC_OSCILLATOR1             = 0x900a # bit 7: enabled, bits 6-0: frequency
VIC_OSCILLATOR2             = 0x900b # bit 7: enabled, bits 6-0: frequency
VIC_OSCILLATOR3             = 0x900c # bit 7: enabled, bits 6-0: frequency
VIC_NOISE                   = 0x900d # bit 7: enabled, bits 6-0: frequency
VIC_AUXILIARY_COLOR_VOLUME  = 0x900e # bits 7-4: auxiliary color, bits 3-0: volume
VIC_BACKGROUND_BORDER_COLOR = 0x900f # bits 7-4: background color, bit 3: not reverse video, bits 2-0: border color
