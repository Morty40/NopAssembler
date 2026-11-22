"""The blitter, which combines two sources, A and B, into a destination, in RAM. Only with the VIC's extended registers on, see VIC_EXTENDED.

The addresses are 22 bits: bits 21-16 in bits 5-0 of the high byte. The steps are in 16ths of a byte, $10 for each byte.
Writing BLITTER_CONTROL with BLITTER_CONTROL_START starts the blit, of BLITTER_LENGTH bytes, and BLITTER_STATUS shows when it is done.
"""

BLITTER_SOURCE_A_LO                = 0xd320
BLITTER_SOURCE_A_MIDDLE            = 0xd321
BLITTER_SOURCE_A_HI                = 0xd322
BLITTER_SOURCE_A_MODULO_LO         = 0xd323 # added to the address after each line
BLITTER_SOURCE_A_MODULO_HI         = 0xd324
BLITTER_SOURCE_A_LINE_LENGTH_LO    = 0xd325 # the bytes of a line
BLITTER_SOURCE_A_LINE_LENGTH_HI    = 0xd326
BLITTER_SOURCE_A_STEP              = 0xd327 # $10 by default
BLITTER_SOURCE_B_LO                = 0xd328
BLITTER_SOURCE_B_MIDDLE            = 0xd329
BLITTER_SOURCE_B_HI                = 0xd32a
BLITTER_SOURCE_B_MODULO_LO         = 0xd32b
BLITTER_SOURCE_B_MODULO_HI         = 0xd32c
BLITTER_SOURCE_B_LINE_LENGTH_LO    = 0xd32d
BLITTER_SOURCE_B_LINE_LENGTH_HI    = 0xd32e
BLITTER_SOURCE_B_STEP              = 0xd32f
BLITTER_DESTINATION_LO             = 0xd330
BLITTER_DESTINATION_MIDDLE         = 0xd331
BLITTER_DESTINATION_HI             = 0xd332
BLITTER_DESTINATION_MODULO_LO      = 0xd333
BLITTER_DESTINATION_MODULO_HI      = 0xd334
BLITTER_DESTINATION_LINE_LENGTH_LO = 0xd335
BLITTER_DESTINATION_LINE_LENGTH_HI = 0xd336
BLITTER_DESTINATION_STEP           = 0xd337
BLITTER_LENGTH_LO                  = 0xd338 # the number of bytes
BLITTER_LENGTH_HI                  = 0xd339
BLITTER_CONTROL                    = 0xd33a # see BLITTER_CONTROL_...
BLITTER_WRITE                      = 0xd33b # see BLITTER_WRITE_...
BLITTER_OPERATION                  = 0xd33e # bits 2-0: the bits to shift source A right, bits 5-3: BLITTER_OPERATION_...
BLITTER_CONTINUE                   = 0xd33f # see BLITTER_CONTINUE_...
BLITTER_STATUS                     = 0xd33f # read: see BLITTER_STATUS_...

BLITTER_CONTROL_START               = 0x01
BLITTER_CONTROL_SOURCE_A_FORWARD    = 0x02 # adds the step, or else subtracts it
BLITTER_CONTROL_SOURCE_B_FORWARD    = 0x04
BLITTER_CONTROL_DESTINATION_FORWARD = 0x08
BLITTER_CONTROL_START_AT_FRAME      = 0x40 # starts at raster line 0
BLITTER_CONTROL_IRQ                 = 0x80 # an interrupt when done

BLITTER_WRITE_SOURCE_B_ZERO       = 0x01 # source B is 0
BLITTER_WRITE_IF_SOURCE_A_ZERO    = 0x02 # with neither of these, or both, it always writes
BLITTER_WRITE_IF_SOURCE_A_NONZERO = 0x04 # e.g. for transparency, with 0 as the transparent color

BLITTER_OPERATION_AND  = 0 << 3
BLITTER_OPERATION_NAND = 1 << 3
BLITTER_OPERATION_NOR  = 2 << 3
BLITTER_OPERATION_OR   = 3 << 3
BLITTER_OPERATION_XOR  = 4 << 3
BLITTER_OPERATION_XNOR = 5 << 3
BLITTER_OPERATION_ADD  = 6 << 3
BLITTER_OPERATION_SUB  = 7 << 3 # source A - source B

BLITTER_CONTINUE_CLEAR_IRQ   = 0x01
BLITTER_CONTINUE_SOURCE_A    = 0x02 # source A continues where the last blit ended
BLITTER_CONTINUE_SOURCE_B    = 0x04
BLITTER_CONTINUE_DESTINATION = 0x08

BLITTER_STATUS_BUSY = 0x01
BLITTER_STATUS_IRQ  = 0x02
