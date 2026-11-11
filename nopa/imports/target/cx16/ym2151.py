"""The YM2151 FM sound chip: its two ports, and the numbers of its internal registers.

Write a register's number to YM2151_ADDRESS, then its value to YM2151_DATA, and wait while the chip is busy.
"""

YM2151_ADDRESS = 0x9f40 # the number of the register to write
YM2151_DATA    = 0x9f41 # written: the register's value. Read: the status, bit 7: busy, bits 0-1: timer A and B overflow

# the registers of the chip, which are numbers, not addresses
YM2151_REGISTER_TEST          = 0x01 # bit 1: LFO reset
YM2151_REGISTER_KEY_ON        = 0x08 # bits 0-2: the channel, bits 3-6: its four operators, on or off
YM2151_REGISTER_NOISE         = 0x0f # bit 7: noise on channel 7, bits 0-4: noise frequency
YM2151_REGISTER_TIMER_A_HI    = 0x10 # bits 2-9 of timer A
YM2151_REGISTER_TIMER_A_LO    = 0x11 # bits 0-1 of timer A
YM2151_REGISTER_TIMER_B       = 0x12
YM2151_REGISTER_TIMER_CONTROL = 0x14 # bits 0-1: load timers A and B, 2-3: their interrupts, 4-5: reset their flags, 7: CSM mode
YM2151_REGISTER_LFO_FREQUENCY = 0x18
YM2151_REGISTER_LFO_DEPTH     = 0x19 # bit 7: 1 for phase, 0 for amplitude modulation depth, bits 0-6: the depth
YM2151_REGISTER_LFO_WAVEFORM  = 0x1b # bits 0-1: saw, square, triangle or noise, bits 6-7: the CT output pins

# one register for each channel: add the channel, 0-7
YM2151_REGISTER_CHANNEL_CONTROL         = 0x20 # bit 7: right, bit 6: left, bits 3-5: feedback, bits 0-2: algorithm
YM2151_REGISTER_KEY_CODE                = 0x28 # bits 4-6: octave, bits 0-3: note
YM2151_REGISTER_KEY_FRACTION            = 0x30 # bits 2-7: between notes
YM2151_REGISTER_MODULATION_SENSITIVITY  = 0x38 # bits 4-6: phase, bits 0-1: amplitude

# one register for each operator: add the channel, 0-7, and 8 times the operator, 0-3 for M1, M2, C1 and C2
YM2151_REGISTER_DETUNE1_MULTIPLE        = 0x40 # bits 4-6: detune 1, bits 0-3: frequency multiple
YM2151_REGISTER_TOTAL_LEVEL             = 0x60 # bits 0-6: attenuation, 0 is loudest
YM2151_REGISTER_KEY_SCALE_ATTACK        = 0x80 # bits 6-7: key scaling, bits 0-4: attack rate
YM2151_REGISTER_DECAY1                  = 0xa0 # bit 7: amplitude modulation on, bits 0-4: decay rate 1
YM2151_REGISTER_DETUNE2_DECAY2          = 0xc0 # bits 6-7: detune 2, bits 0-4: decay rate 2
YM2151_REGISTER_DECAY1_LEVEL_RELEASE    = 0xe0 # bits 4-7: decay level 1, bits 0-3: release rate
