# Changelog

What's new in Nop Assembler.

## [0.1.0] - unreleased

The first release.

### Added
- multi-pass 6502 assembler, with automatic zero page addressing and the stable illegal instructions
- Python expressions, f-strings and lambdas in operands and directives
- generators: Python functions that return assembly code
- local labels, named after the global label before them, so `_loop` after `start:` can be used from anywhere as `start_loop`
- labels can't be in all capitals, which are for constants, so a label can't replace a built-in constant
- zero page variable allocation, `.repeat`, `.for` and `.if` blocks
- `ref("label")`, to only assemble an `.if` block if its label is referenced
- `has("instruction")`, to choose an `.if` path by what the current cpu can assemble
- `.optional` blocks, only assembled if one of their labels is referenced
- `.section "name", $address`, named sections that continue where they stopped, to store code and data in separate areas of memory
- PETSCII and screen code text encodings, and your own encoding tables
- `.cpu` and `--cpu`, to choose the 6502, the 65C02, the Rockwell R65C02 or the WDC W65C02, when assembling and disassembling
- `.assert` to check conditions while assembling, e.g. the memory layout
- import of source files, Python files, binary files and SID music
- generic 6502 generators and symbols, always imported
- symbols defined on the command line: `-D NAME=VALUE`, or `-D NAME` for `True`
- target imports with `-t c128|c16|c64|cx16|plus4|vic20`, such as the C64 hardware (VIC, SID, CIA, KERNAL, BASIC). `cx16`, for the Commander X16, is experimental
- BASIC lines with the keywords as tokens, in the BASIC version of the target: 2.0, 3.5 or 7.0
- `.prg` and binary output, chosen with `--format prg|bin`, and a memory map after a successful assembly
- labels file, as Python assignments: `nopa game.asm -l game.py`
- VICE monitor commands file with labels and `.break` breakpoints: `nopa game.asm --vice game.vmc`
- disassembler: `nopa -d <binFile>`, to a file with `-o` or printed, with the names from a labels file with `-l`, and each instruction commented as in a machine code monitor, with its address and bytes
- Python API: `nopa.assembleFile`, `nopa.disassembleFile` and `nopa.Context`
- warnings and errors on stderr, and exit code 1 on errors
- `nopa --version` and `nopa -h`
- requires Python 3.11 or later

[0.1.0]: https://github.com/Morty40/NopAssembler/releases/tag/v0.1.0
