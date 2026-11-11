"""The registers of the two VIA 6522 chips."""

VIA1_DATA_PORTB              = 0x9110 # bit 0: RS-232 received data, 1: RTS, 2: DTR, 3: ring indicator, 4: DCD, 6: CTS, 7: DSR
VIA1_DATA_PORTA              = 0x9111 # bit 0: serial CLK in, 1: serial DATA in, 2-4: joystick 0-2, 5: light pen and fire button, 6: cassette switch, 7: serial ATN out
VIA1_DATA_DIRECTION_PORTB    = 0x9112
VIA1_DATA_DIRECTION_PORTA    = 0x9113
VIA1_TIMER1_COUNTER_LO       = 0x9114
VIA1_TIMER1_COUNTER_HI       = 0x9115
VIA1_TIMER1_LATCH_LO         = 0x9116
VIA1_TIMER1_LATCH_HI         = 0x9117
VIA1_TIMER2_LO               = 0x9118
VIA1_TIMER2_HI               = 0x9119
VIA1_SERIAL_SHIFT            = 0x911a
VIA1_AUXILIARY_CONTROL       = 0x911b
VIA1_PERIPHERAL_CONTROL      = 0x911c # bit 0: RESTORE key, bits 1-3: cassette motor, bit 4: RS-232 receive interrupt, bits 5-7: RS-232 transmit data
VIA1_INTERRUPT_FLAG          = 0x911d
VIA1_INTERRUPT_ENABLE        = 0x911e
VIA1_DATA_PORTA_NO_HANDSHAKE = 0x911f

VIA2_DATA_PORTB              = 0x9120 # keyboard column scan. Bit 3: cassette write, 7: joystick 3
VIA2_DATA_PORTA              = 0x9121 # keyboard row scan
VIA2_DATA_DIRECTION_PORTB    = 0x9122
VIA2_DATA_DIRECTION_PORTA    = 0x9123
VIA2_TIMER1_COUNTER_LO       = 0x9124 # timer 1 gives the BASIC and KERNAL interrupt, 60 times a second
VIA2_TIMER1_COUNTER_HI       = 0x9125
VIA2_TIMER1_LATCH_LO         = 0x9126
VIA2_TIMER1_LATCH_HI         = 0x9127
VIA2_TIMER2_LO               = 0x9128
VIA2_TIMER2_HI               = 0x9129
VIA2_SERIAL_SHIFT            = 0x912a
VIA2_AUXILIARY_CONTROL       = 0x912b
VIA2_PERIPHERAL_CONTROL      = 0x912c # bit 0: cassette read, bits 1-3: serial clock out, bit 4: serial SRQ in, bits 5-7: serial data out
VIA2_INTERRUPT_FLAG          = 0x912d
VIA2_INTERRUPT_ENABLE        = 0x912e
VIA2_DATA_PORTA_NO_HANDSHAKE = 0x912f
