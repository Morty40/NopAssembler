"""The registers of the VERA video chip, and its VRAM layout."""

VERA_ADDRESS_LO        = 0x9f20 # the VRAM address of the selected data register, bits 0-7
VERA_ADDRESS_MID       = 0x9f21 # bits 8-15
VERA_ADDRESS_HI        = 0x9f22 # bit 0: address bit 16, bit 3: decrement, bits 4-7: increment
VERA_DATA0             = 0x9f23
VERA_DATA1             = 0x9f24
VERA_CONTROL           = 0x9f25 # bit 0: address select, bits 1-6: DC select, bit 7: reset
VERA_INTERRUPT_ENABLE  = 0x9f26 # bit 0: VSYNC, 1: LINE, 2: SPRCOL, 3: AFLOW, 6: scan line bit 8, 7: IRQ line bit 8
VERA_INTERRUPT_STATUS  = 0x9f27 # bit 0: VSYNC, 1: LINE, 2: SPRCOL, 3: AFLOW, 4-7: sprite collisions
VERA_IRQ_LINE          = 0x9f28 # written: the IRQ line, bits 0-7
VERA_SCAN_LINE         = 0x9f28 # read: the scan line, bits 0-7

# with DC select 0 in VERA_CONTROL
VERA_VIDEO             = 0x9f29 # output mode, chroma disable, 240p, layer and sprite enables, current field
VERA_HORIZONTAL_SCALE  = 0x9f2a
VERA_VERTICAL_SCALE    = 0x9f2b
VERA_BORDER_COLOR      = 0x9f2c

# with DC select 1 in VERA_CONTROL: the active display
VERA_HORIZONTAL_START  = 0x9f29 # bits 2-9
VERA_HORIZONTAL_STOP   = 0x9f2a # bits 2-9
VERA_VERTICAL_START    = 0x9f2b # bits 1-8
VERA_VERTICAL_STOP     = 0x9f2c # bits 1-8

VERA_LAYER0_CONFIG     = 0x9f2d # map height and width, T256C, bitmap mode, color depth
VERA_LAYER0_MAPBASE    = 0x9f2e # map base address, bits 9-16
VERA_LAYER0_TILEBASE   = 0x9f2f # tile base address, bits 11-16, tile height and width
VERA_LAYER0_HSCROLL_LO = 0x9f30
VERA_LAYER0_HSCROLL_HI = 0x9f31 # bits 8-11
VERA_LAYER0_VSCROLL_LO = 0x9f32
VERA_LAYER0_VSCROLL_HI = 0x9f33 # bits 8-11

VERA_LAYER1_CONFIG     = 0x9f34
VERA_LAYER1_MAPBASE    = 0x9f35
VERA_LAYER1_TILEBASE   = 0x9f36
VERA_LAYER1_HSCROLL_LO = 0x9f37
VERA_LAYER1_HSCROLL_HI = 0x9f38
VERA_LAYER1_VSCROLL_LO = 0x9f39
VERA_LAYER1_VSCROLL_HI = 0x9f3a

VERA_AUDIO_CONTROL     = 0x9f3b # PCM volume, stereo, 16-bit, FIFO empty, FIFO full or reset
VERA_AUDIO_RATE        = 0x9f3c # the PCM sample rate
VERA_AUDIO_DATA        = 0x9f3d # the audio FIFO, write only
VERA_SPI_DATA          = 0x9f3e
VERA_SPI_CONTROL       = 0x9f3f # select, slow clock, busy

# the VRAM layout, 128K
VERA_VRAM_TEXT         = 0x1b000 # the text screen after a reset: a character and a color byte each, 256 bytes a line
VERA_VRAM_PSG          = 0x1f9c0 # the sound generator, 16 voices of 4 bytes
VERA_VRAM_PALETTE      = 0x1fa00 # 256 colors of 2 bytes
VERA_VRAM_SPRITES      = 0x1fc00 # the attributes of 128 sprites, 8 bytes each
