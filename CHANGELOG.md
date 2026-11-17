# Changelog

What's new in Nop Assembler.

## [0.1.0] - unreleased

The first release: a 6502 cross assembler for Commodore computers, where every expression is Python, and a disassembler.

### Added
- multi-pass assembler for the 6502, with the stable illegal instructions, and for the 65C02, Rockwell R65C02 and WDC W65C02, chosen with `--cpu` or `.cpu`
- automatic zero page addressing
- Python expressions, f-strings and lambdas in operands and directives, and blocks of Python code with `.python`
- generators: Python functions that return assembly code, with their own local labels for each call, and built-in ones such as `@ldax()` and `@pushRegisters()`
- local labels, which can also be used from anywhere by their full name, such as `start_loop`
- the current address as `_`, such as `jmp _`, which Python code can also read and assign
- constants, and zero page variables with `zp(size)`, e.g. `pointer = zp(2)`
- `.repeat` and `.if` blocks, `.for` loops over any Python iterable, as in Python, such as `.for i in range(8)` or `.for x, y in points`, conditions with `ref()` and `has()`, and `.optional` code that is only assembled when it is used
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

[0.1.0]: https://github.com/Morty40/NopAssembler/releases/tag/v0.1.0
