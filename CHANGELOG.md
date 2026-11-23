# Changelog

What's new in Nop Assembler.

## [Unreleased]

## [0.2.0] - 2026-11-23

### Added
- `@basic.float(number)`, a number in BASIC's 5-byte floating point format, for the ROM's floating point routines
- `@basic.load(filename)`, the lines of a BASIC listing in a text file, such as `10 PRINT "HELLO"`, with `{expression}` filled in
- the C64 DTV's cpu, `CPU_DTV` and `--cpu DTV`: the 6502's instructions, also the illegal ones, and `bra`, `sac` and `sir`
- the `dtv` target, for the C64 DTV: the C64's symbols, and the DTV's extended VIC registers and palette, cpu registers, memory mapper, flash, DMA and blitter
- the default cpu of each target, `CPU_DEFAULT_TYPE`, which `-t` assembles for unless `--cpu` chooses another, e.g. `CPU_W65C02` on the `cx16`

### Changed
- the `cx16` target assembles for the W65C02, as the X16 has a WDC 65C02, so without the 6502's illegal instructions
- the BASIC generators are in the namespace `basic`: `@basic.start()`, `@basic.line()`, `@basic.sys()` and `@basic.end()`, which were `@basicStart()`, `@basicLine()`, `@basicSys()` and `@basicEnd()`

### Removed
- `BASIC_ROM`, the address of the BASIC ROM, from the targets

## [0.1.0] - 2026-11-20

The first release: a 6502 cross assembler for Commodore computers, where every expression is Python, and a disassembler.

### Added
- multi-pass assembler for the 6502, with the stable illegal instructions, and for the 65C02, Rockwell R65C02 and WDC W65C02, chosen with `--cpu` or `.cpu`
- automatic zero page addressing
- Python expressions, f-strings and lambdas in operands and directives, directive arguments as in a Python call, unpacked with `*` or given by name, such as `.byte *table` or `.binary "music.sid", offset=$7e`, and blocks of Python code with `.python`
- generators: Python functions that return assembly code, with their own local labels for each call, and built-in ones such as `@ldax()` and `@pushRegisters()`
- local labels, which can also be used from anywhere by their full name, such as `start_loop`
- the current address as `_`, such as `jmp _`, which Python code can also read and assign
- constants, and zero page variables with `zp(size)`, e.g. `pointer = zp(2)`
- `.repeat` blocks, `.if` blocks with `.elif` and `.else`, `.for` loops over any Python iterable, as in Python, such as `.for i in range(8)` or `.for x, y in points`, conditions with `ref()` and `has()`, and `.optional` code that is only assembled when it is used
- named sections with `.section`, to store code and data in separate areas of memory
- data with `.byte`, `.word`, `.text`, `.string` and `.bits`, with text in PETSCII, screen codes or your own encoding
- tables with `.bytefill` and `.wordfill`, of zeros or the values of a function of the index: a lambda, such as `lambda x: x*3`, a built-in, or a function or method from Python code
- import of source and Python files, also into a namespace, such as `spr.draw` or `util.double()`, of binary files, and of SID music on the C64
- targets with `-t` for the C128, C16, C64, Plus/4 and VIC-20, and an experimental one for the Commander X16: hardware registers, KERNAL and BASIC routines, and BASIC lines with their keywords as tokens
- symbols defined on the command line with `-D`
- `.assert`, `.print`, `.warning` and `.error`, to check and report while assembling
- `.prg` or binary output, and a map of the memory used
- a labels file, as Python assignments, and VICE monitor commands with labels and `.break` breakpoints
- a disassembler, which turns a program into source that assembles to the same bytes, with the names from a labels file, and a monitor view of every instruction
- a Python API, `nopa.assembleFile` and `nopa.disassembleFile`, e.g. for unit tests of 6502 code
- requires Python 3.11 or later

[Unreleased]: https://github.com/Morty40/NopAssembler/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Morty40/NopAssembler/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Morty40/NopAssembler/releases/tag/v0.1.0
