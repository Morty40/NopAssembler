"""The DMA engine, which copies between RAM and flash. Only with the VIC's extended registers on, see VIC_EXTENDED.

The addresses are 22 bits: bits 21-16 in bits 5-0 of the high byte, with the memory in bits 7-6, DMA_MEMORY_...
Writing DMA_CONTROL with DMA_CONTROL_START starts the copy, of DMA_LENGTH bytes, and DMA_STATUS shows when it is done.
"""

DMA_SOURCE_LO                  = 0xd300
DMA_SOURCE_MIDDLE              = 0xd301
DMA_SOURCE_HI                  = 0xd302 # bits 5-0: bits 21-16, bits 7-6: DMA_MEMORY_...
DMA_DESTINATION_LO             = 0xd303
DMA_DESTINATION_MIDDLE         = 0xd304
DMA_DESTINATION_HI             = 0xd305
DMA_SOURCE_STEP_LO             = 0xd306 # added to the address for each byte
DMA_SOURCE_STEP_HI             = 0xd307
DMA_DESTINATION_STEP_LO        = 0xd308
DMA_DESTINATION_STEP_HI        = 0xd309
DMA_LENGTH_LO                  = 0xd30a # the number of bytes, 0 for 65536
DMA_LENGTH_HI                  = 0xd30b
DMA_SOURCE_MODULO_LO           = 0xd30c # added to the address after each line, with DMA_MODULO_SOURCE
DMA_SOURCE_MODULO_HI           = 0xd30d
DMA_DESTINATION_MODULO_LO      = 0xd30e
DMA_DESTINATION_MODULO_HI      = 0xd30f
DMA_SOURCE_LINE_LENGTH_LO      = 0xd310 # the bytes of a line
DMA_SOURCE_LINE_LENGTH_HI      = 0xd311
DMA_DESTINATION_LINE_LENGTH_LO = 0xd312
DMA_DESTINATION_LINE_LENGTH_HI = 0xd313
DMA_CONTINUE                   = 0xd31d # see DMA_CONTINUE_...
DMA_MODULO                     = 0xd31e # see DMA_MODULO_...
DMA_CONTROL                    = 0xd31f # see DMA_CONTROL_...
DMA_STATUS                     = 0xd31f # read: see DMA_STATUS_...

DMA_MEMORY_FLASH      = 0x00
DMA_MEMORY_RAM        = 0x40
DMA_MEMORY_RAM_AND_IO = 0x80 # RAM, with the I/O registers at $d000-$dfff

DMA_CONTINUE_CLEAR_IRQ   = 0x01
DMA_CONTINUE_SOURCE      = 0x02 # the source continues where the last copy ended
DMA_CONTINUE_DESTINATION = 0x08

DMA_MODULO_SOURCE      = 0x01
DMA_MODULO_DESTINATION = 0x02

DMA_CONTROL_START               = 0x01
DMA_CONTROL_SWAP                = 0x02 # swaps the bytes of the source and destination
DMA_CONTROL_SOURCE_FORWARD      = 0x04 # adds the step, or else subtracts it
DMA_CONTROL_DESTINATION_FORWARD = 0x08
DMA_CONTROL_START_AFTER_BLITTER = 0x20 # starts when the blitter is done
DMA_CONTROL_START_AT_FRAME      = 0x40 # starts at raster line 0
DMA_CONTROL_IRQ                 = 0x80 # an interrupt when done

DMA_STATUS_BUSY = 0x01
DMA_STATUS_IRQ  = 0x02
