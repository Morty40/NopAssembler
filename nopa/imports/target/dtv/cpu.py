"""The cpu, which the target assembles for unless --cpu chooses another, and its registers.

The DTV's cpu has 16 registers. sac #$nm makes register n the accumulator for writing and register m for reading,
and sir #$nm makes register n y and register m x, see cpuAccumulators and cpuIndexRegisters. Registers 8 to 15
control the cpu and the memory, e.g. sac #$a0, lda #$10, sac #$00 moves the zero page to $1000.
"""

CPU_DEFAULT_TYPE = CPU_DTV # the DTV's 6510

CPU_REGISTER_A         = 0
CPU_REGISTER_Y         = 1
CPU_REGISTER_X         = 2
CPU_REGISTER_ACCESS    = 8  # 2 bits for each 16K bank, bits 1-0 for $0000-$3fff: %00 flash, %01 RAM (the default, $55)
CPU_REGISTER_CONTROL   = 9  # see CPU_CONTROL_...
CPU_REGISTER_ZERO_PAGE = 10 # the page of RAM used as zero page, 0 by default
CPU_REGISTER_STACK     = 11 # the page of RAM used as the stack, 1 by default
CPU_REGISTER_BANK0     = 12 # the 16K segment of the 2M RAM, or flash, at $0000-$3fff, 0 by default
CPU_REGISTER_BANK1     = 13 # at $4000-$7fff, 1 by default
CPU_REGISTER_BANK2     = 14 # at $8000-$bfff, 2 by default
CPU_REGISTER_BANK3     = 15 # at $c000-$ffff, 3 by default

CPU_ACCESS_FLASH = 0b00
CPU_ACCESS_RAM   = 0b01

CPU_CONTROL_SKIP_CYCLE = 0x01 # leaves out the dummy cycles, so many instructions are faster
CPU_CONTROL_BURST      = 0x02 # burst mode: faster instruction fetches, in the banks with CPU_ACCESS_RAM

cpuAccumulators = lambda write, read: ((write & 0xf) << 4) | (read & 0xf) # the operand of sac
cpuIndexRegisters = lambda y, x: ((y & 0xf) << 4) | (x & 0xf)              # the operand of sir
