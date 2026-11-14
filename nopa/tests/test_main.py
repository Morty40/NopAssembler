#! /usr/bin/env python3
"""Tests of the command line."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from .. import __version__
from .. import assemble
from .. import disassemble
from ..context import Context
from ..main import binary, main, prg, printMemoryUse, sortedLabels


class TestMain(unittest.TestCase):
    """Tests of the command line."""

    def _main(self, arguments: list):
        """Run main() with the arguments. Returns the exit code, and the output and error output."""
        with mock.patch.object(sys, 'argv', ['nopa'] + arguments), \
             contextlib.redirect_stdout(io.StringIO()) as output, \
             contextlib.redirect_stderr(io.StringIO()) as errors, \
             self.assertRaises(SystemExit) as raised:
            main()
        return raised.exception.code, output.getvalue(), errors.getvalue()

    def testUsage(self):
        """Missing or incorrect arguments print the usage, and exit with 2."""
        for arguments in [[], ['-o', 'x.prg'], ['-d'], ['x.asm', 'extra'], ['-x'],
                          ['x.asm', '--vice'], ['x.asm', '-t'], ['x.asm', '-t', 'amiga'], ['-d', 'x.prg', '-t', 'c64'],
                          ['x.asm', '-l'], ['x.asm', '--labels'], ['x.asm', '--cpu'], ['x.asm', '--cpu', 'z80'],
                          ['x.asm', '--format'], ['x.asm', '--format', 'd64'], ['-d', 'x.prg', '--format', 'bin'],
                          ['x.asm', '-D'], ['x.asm', '-D', '1X=2'], ['x.asm', '-D', '=2'], ['-d', 'x.prg', '-D', 'X'],
                          ['x.asm', '-D', '_x=1'], ['x.asm', '-D', '_=1'], ['x.asm', '-D', 'if'], ['x.asm', '-D', 'lda=1'], ['x.asm', '-D', 'stz']]:
            with self.subTest(arguments=arguments):
                code, output, errors = self._main(arguments)
                self.assertEqual(code, 2)
                self.assertIn('usage: nopa', errors)

    def testInterrupted(self):
        """Ctrl-C prints a message, without a traceback, and exits with 130."""
        for module, function, arguments in [(assemble, 'assembleFile', ['x.asm']),
                                            (disassemble, 'disassembleFile', ['-d', 'x.prg'])]:
            with self.subTest(function=function), mock.patch.object(module, function, side_effect=KeyboardInterrupt):
                code, output, errors = self._main(arguments)
                self.assertEqual(code, 130)
                self.assertEqual(output, '')
                self.assertEqual(errors, 'error: Interrupted\n')

    def testHelp(self):
        """-h prints the help, with each option, and exits with 0."""
        code, output, errors = self._main(['-h'])
        self.assertEqual(code, 0)
        self.assertIn('[-d] [-o OUTFILE]', output)
        self.assertIn('positional arguments:\n  file ', output)
        self.assertIn('-d, --disassemble', output)
        self.assertIn('--output OUTFILE', output) # Python 3.13 shows '-o, --output OUTFILE', older versions '-o OUTFILE, --output OUTFILE'
        self.assertIn('--labels LABELSFILE', output)
        self.assertIn('--vice VICEFILE', output)
        self.assertIn('--cpu {6502,65C02,R65C02,W65C02}', output)
        self.assertIn('--format {prg,bin}', output)
        self.assertIn('--version', output)
        self.assertIn(f'Nop Assembler v{__version__}', output)

    def testVersion(self):
        """--version prints the package version and copyright, and exits with 0."""
        import nopa
        code, output, errors = self._main(['--version'])
        self.assertEqual(code, 0)
        self.assertEqual(output, f'Nop Assembler v{nopa.__version__} (c) Morten Perriard 2021-2026\n')

    def testTarget(self):
        """-t and --target choose the target imports, and without them there are none."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile = os.path.join(directory, 'test.asm')
            with open(asmFile, 'w') as f:
                f.write('.print BASIC_START_ADDRESS\n')
            for arguments, expected in [(['-t', 'c64'], '2049'), (['--target', 'vic20'], '4097'), (['-t', 'c16'], '4097'), (['--target=c64'], '2049')]:
                with self.subTest(arguments=arguments):
                    code, output, errors = self._main([asmFile] + arguments)
                    self.assertEqual(code, 0, errors)
                    self.assertEqual(output.splitlines()[0], expected)
            code, output, errors = self._main([asmFile])
            self.assertEqual(code, 1)
            self.assertIn("Name 'BASIC_START_ADDRESS' is not defined", errors)

    def testDefine(self):
        """-D and --define assign a symbol, True without a value, before the source."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile = os.path.join(directory, 'test.asm')
            with open(asmFile, 'w') as f:
                f.write('.print PAL, size, DEBUG\n')
            code, output, errors = self._main([asmFile, '-D', 'PAL=45', '--define', 'size=$10', '-D', 'DEBUG'])
            self.assertEqual(code, 0, errors)
            self.assertEqual(output.splitlines()[:3], ['45', '16', 'True'])
            code, output, errors = self._main([asmFile, '-D', 'PAL=x', '-D', 'size=1', '-D', 'DEBUG'])
            self.assertEqual(code, 1)
            self.assertIn('<command-line>:1: error: Name \'x\' is not defined', errors)

    def testDefineInvalid(self):
        """A -D name must be a name the source can use: not a local label, a Python keyword or built-in, or a mnemonic."""
        for define in ['_x=1', 'if=1', 'lda=1', 'len=1', 'print', '2x=1', 'my-x=1', '=1']:
            with self.subTest(define=define):
                code, output, errors = self._main(['test.asm', '-D', define])
                self.assertEqual(code, 2)
                self.assertIn(f'Invalid define: {define}', errors)

    def testAssemble(self):
        """Assembling prints the .print output and the memory use, sends warnings to stderr, and saves the -o file."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, prgFile = os.path.join(directory, 'a.asm'), os.path.join(directory, 'a.prg')
            with open(asmFile, 'w') as f:
                f.write('.print "hi"\n.warning "careful"\nlda #1\n')
            code, output, errors = self._main([asmFile, '-o', prgFile])
            self.assertEqual(code, 0, errors)
            self.assertIn('hi', output.splitlines())
            self.assertIn('Memory used: $1000-$1001 (2 bytes)', output.splitlines())
            self.assertEqual(errors, f'{asmFile}:2: warning: careful\n')
            with open(prgFile, 'rb') as f:
                self.assertEqual(f.read(), bytes([0x00, 0x10, 0xa9, 0x01]))

    def testAssembleError(self):
        """With an error, assembling still prints the .print output, but not the memory use, and saves nothing. Exits with 1."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, prgFile = os.path.join(directory, 'a.asm'), os.path.join(directory, 'a.prg')
            with open(asmFile, 'w') as f:
                f.write('.print "hi"\n.error "stop"\n')
            code, output, errors = self._main([asmFile, '-o', prgFile])
            self.assertEqual(code, 1)
            self.assertIn('hi', output.splitlines())
            self.assertNotIn('Memory used', output)
            self.assertEqual(errors, f'{asmFile}:2: error: stop\n')
            self.assertFalse(os.path.exists(prgFile))

    def testAssembleMissingFolder(self):
        """A file that can't be written exits with 1, and an error on stderr, after the .print output and the warnings."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, missingFolder = os.path.join(directory, 'a.asm'), os.path.join(directory, 'missing', 'a.prg')
            with open(asmFile, 'w') as f:
                f.write('.print "hi"\n.warning "careful"\nnop\n')
            code, output, errors = self._main([asmFile, '-o', missingFolder])
            self.assertEqual(code, 1)
            self.assertIn('hi', output.splitlines())
            self.assertEqual(errors, f'{asmFile}:2: warning: careful\nerror: No such file or directory: "{missingFolder}"\n')

    def testPrg(self):
        """A .prg file is the load address, the lowest address used or $1000 if nothing is stored,
        then the bytes from there to the highest address, gaps as 0."""
        for memory, expected in [({0x2000: 1, 0x1fff: 2}, [0xff, 0x1f, 2, 1]),
                                 ({0x1000: 1, 0x1002: 3}, [0x00, 0x10, 1, 0, 3]),
                                 ({},                     [0x00, 0x10])]:
            with self.subTest(memory=memory):
                context = Context({})
                context.memory = memory
                self.assertEqual(list(prg(context)), expected)

    def testBinary(self):
        """A .bin file is the same as a .prg file, without the load address."""
        for memory, expected in [({0x2000: 1, 0x1fff: 2}, [2, 1]),
                                 ({0x1000: 1, 0x1002: 3}, [1, 0, 3]),
                                 ({},                     [])]:
            with self.subTest(memory=memory):
                context = Context({})
                context.memory = memory
                self.assertEqual(list(binary(context)), expected)

    def testFormat(self):
        """--format chooses the file -o writes: prg, the default, starts with the load address, bin doesn't."""
        for arguments, expected in [([],                  [0x00, 0x10, 0xa9, 0x01]),
                                    (['--format', 'prg'], [0x00, 0x10, 0xa9, 0x01]),
                                    (['--format', 'bin'], [0xa9, 0x01])]:
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as directory:
                asmFile, outFile = os.path.join(directory, 'a.asm'), os.path.join(directory, 'a.out')
                with open(asmFile, 'w') as f:
                    f.write('lda #1\n')
                code, output, errors = self._main([asmFile, '-o', outFile] + arguments)
                self.assertEqual(code, 0, errors)
                with open(outFile, 'rb') as f:
                    self.assertEqual(list(f.read()), expected)

    def testSortedLabels(self):
        """The labels, sorted by address, with local labels as global_local, and generator labels
        as generator1_local. Other symbols, such as constants and zero page variables, are not included."""
        source = 'VALUE = 5\ncounter = zp(1)\nstart: lda #VALUE\n_loop: dex\nbne _loop\nrts\n' \
                 '.python\ndef wait():\n    return "_x: dex\\nbne _x"\n.end\n@wait()\n'
        with tempfile.TemporaryDirectory() as directory:
            asmFile = os.path.join(directory, 'test.asm')
            with open(asmFile, 'w') as f:
                f.write(source)
            context = assemble.assembleFile(asmFile)
        self.assertEqual(sortedLabels(context), [(0x1000, 'start'), (0x1002, 'start_loop'), (0x1006, 'wait1_x')])

    def testNamespacedLabels(self):
        """The labels of a source file imported into a namespace have their full names, e.g. spr.draw and spr.draw_loop,
        written with _ in the VICE monitor commands, spr_draw, as VICE labels are a single word."""
        sprites = ('draw: ldx #2\n'
                   '_loop: dex\n'
                   'bne _loop\n'
                   'rts\n')
        with tempfile.TemporaryDirectory() as directory:
            asmFile, viceFile = os.path.join(directory, 'test.asm'), os.path.join(directory, 'test.vmc')
            with open(asmFile, 'w') as f:
                f.write('.import "sprites.asm", "spr"\n')
            with open(os.path.join(directory, 'sprites.asm'), 'w') as f:
                f.write(sprites)
            self.assertEqual(sortedLabels(assemble.assembleFile(asmFile)), [(0x1000, 'spr.draw'), (0x1002, 'spr.draw_loop')])
            code, output, errors = self._main([asmFile, '--vice', viceFile])
            self.assertEqual(code, 0, errors)
            with open(viceFile) as f:
                self.assertEqual(f.read(), 'al C:1000 .spr_draw\nal C:1002 .spr_draw_loop\n')

    def testViceCommands(self):
        """--vice writes a VICE monitor commands file: the labels, then the .break breakpoints.
        The memory use doesn't list the labels."""
        source = 'start: nop\n.break\nnop\n.break "RL > $40"\nrts\n'
        expected = 'al C:1000 .start\nbreak C:1001\nbreak C:1002 if RL > $40\n'
        with tempfile.TemporaryDirectory() as directory:
            asmFile, viceFile = os.path.join(directory, 'test.asm'), os.path.join(directory, 'test.vmc')
            with open(asmFile, 'w') as f:
                f.write(source)
            code, output, errors = self._main([asmFile, '--vice', viceFile])
            self.assertEqual(code, 0, errors)
            with open(viceFile) as f:
                self.assertEqual(f.read(), expected)
            self.assertNotIn('start', output)
            code, output, errors = self._main(['-d', asmFile, '--vice', viceFile]) # only when assembling
            self.assertEqual(code, 2)
            self.assertIn('--vice can only be used when assembling', errors)

    def testLabels(self):
        """-l writes the labels as Python assignments."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, labelsFile = os.path.join(directory, 'test.asm'), os.path.join(directory, 'test.py')
            with open(asmFile, 'w') as f:
                f.write('start: ldx #5\n_loop: dex\nbne _loop\nrts\n')
            for option in ['-l', '--labels']:
                with self.subTest(option=option):
                    code, output, errors = self._main([asmFile, option, labelsFile])
                    self.assertEqual(code, 0, errors)
                    with open(labelsFile) as f:
                        self.assertEqual(f.read(), 'start = 0x1000\nstart_loop = 0x1002\n')

    def testNamespacedLabelsFile(self):
        """The labels of a namespace are written with _ for ., e.g. spr_draw for spr.draw, as in the VICE monitor
        commands, so every line of the labels file is still name = address, for scripts and other tools."""
        expected = ('start = 0x1000\n'
                    'spr_draw = 0x1001\n'
                    'spr_util_plot = 0x1002\n')
        with tempfile.TemporaryDirectory() as directory:
            files = {'test.asm':    'start: rts\n.import "sprites.asm", "spr"\n',
                     'sprites.asm': 'draw: rts\n.import "plot.asm", "util"\n',
                     'plot.asm':    'plot: rts\n',
                     'other.asm':   '.import "game.py"\njsr spr_util_plot\n'}
            for name, text in files.items():
                with open(os.path.join(directory, name), 'w') as f:
                    f.write(text)
            labelsFile = os.path.join(directory, 'game.py')
            code, output, errors = self._main([os.path.join(directory, 'test.asm'), '-l', labelsFile])
            self.assertEqual(code, 0, errors)
            with open(labelsFile) as f:
                self.assertEqual(f.read(), expected)
            context = assemble.assembleFile(os.path.join(directory, 'other.asm'))
            self.assertEqual(context.errors, [])
            self.assertEqual(context.memory, {0x1000: 0x20, 0x1001: 0x02, 0x1002: 0x10})

    def testLabelCollision(self):
        """Two labels that are written with the same name, e.g. spr_draw and spr.draw, are an error,
        and the labels file and the VICE monitor commands aren't written."""
        with tempfile.TemporaryDirectory() as directory:
            files = {'test.asm': 'spr_draw: nop\n.import "sprites.asm", "spr"\n', 'sprites.asm': 'draw: rts\n'}
            for name, text in files.items():
                with open(os.path.join(directory, name), 'w') as f:
                    f.write(text)
            labelsFile, viceFile = os.path.join(directory, 'test.py'), os.path.join(directory, 'test.vmc')
            code, output, errors = self._main([os.path.join(directory, 'test.asm'), '-l', labelsFile, '--vice', viceFile])
            self.assertEqual(code, 1)
            self.assertIn('error: Labels "spr.draw" and "spr_draw" are both written as "spr_draw"', errors)
            self.assertFalse(os.path.exists(labelsFile))
            self.assertFalse(os.path.exists(viceFile))

    def testLabelsDisassemble(self):
        """With -d, -l reads the labels, and the disassembly uses their names."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, prgFile, labelsFile = (os.path.join(directory, name) for name in ['test.asm', 'test.prg', 'test.py'])
            with open(asmFile, 'w') as f:
                f.write('start: ldx #5\n_loop: dex\nbne _loop\nrts\n')
            code, output, errors = self._main([asmFile, '-o', prgFile, '-l', labelsFile])
            self.assertEqual(code, 0, errors)
            code, output, errors = self._main(['-d', prgFile, '-l', labelsFile])
            self.assertEqual(code, 0, errors)
            lines = [line.split(';')[0].strip() for line in output.splitlines()] # without the monitor comments
            for line in ['start:', 'start_loop:', 'bne start_loop']:
                self.assertIn(line, lines)

    def testNamespacedLabelsDisassemble(self):
        """The disassembly uses the labels of a namespace by their names in the labels file, e.g. spr_draw,
        and assembles to the same bytes."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, prgFile, labelsFile, sourceFile = (os.path.join(directory, name)
                                                        for name in ['test.asm', 'test.prg', 'test.py', 'source.asm'])
            with open(asmFile, 'w') as f:
                f.write('start: jsr spr.draw\nrts\n.import "sprites.asm", "spr"\n')
            with open(os.path.join(directory, 'sprites.asm'), 'w') as f:
                f.write('draw: ldx #5\n_loop: dex\nbne _loop\nrts\n')
            code, output, errors = self._main([asmFile, '-o', prgFile, '-l', labelsFile])
            self.assertEqual(code, 0, errors)
            code, output, errors = self._main(['-d', prgFile, '-l', labelsFile, '-o', sourceFile])
            self.assertEqual(code, 0, errors)
            with open(sourceFile) as f:
                lines = [line.split(';')[0].strip() for line in f.read().splitlines()] # without the monitor comments
            for line in ['jsr spr_draw', 'spr_draw:', 'spr_draw_loop:', 'bne spr_draw_loop']:
                self.assertIn(line, lines)
            self.assertEqual(assemble.assembleFile(sourceFile).memory, assemble.assembleFile(asmFile).memory)

    def testOutputOrder(self):
        """With stderr in the same pipe as stdout (2>&1), .print output comes before the warnings, as on a terminal."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with tempfile.TemporaryDirectory() as directory:
            asmFile = os.path.join(directory, 'test.asm')
            with open(asmFile, 'w') as f:
                f.write('.print "hi"\n.warning "careful"\n')
            output = subprocess.run([sys.executable, '-m', 'nopa.main', asmFile], cwd=root,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout
        lines = [line.split('/')[-1] for line in output.splitlines()]
        self.assertEqual(lines[:2], ['hi', 'test.asm:2: warning: careful'])

    def testMissingSource(self):
        """A missing source exits with 1, and an error on stderr."""
        with tempfile.TemporaryDirectory() as directory:
            missingFile = os.path.join(directory, 'missing.asm')
            code, output, errors = self._main([missingFile])
            self.assertEqual(code, 1)
            self.assertEqual(errors, f'error: No such file or directory: "{missingFile}"\n')

    def testMemoryUse(self):
        """The page map shows each page as unused, partly used, or full."""
        context = Context({})
        context.memory = {address: 0 for address in range(0x1000, 0x1180)} # page $10 full, page $11 partly used
        with contextlib.redirect_stdout(io.StringIO()) as output:
            printMemoryUse(context)
        self.assertIn('Pages used: 1 full, 1 partial', output.getvalue())
        self.assertIn('$1000: #+..............', output.getvalue())

    def testMemoryUseOutput(self):
        """The whole output: the range, the page counts, and a map of 16 lines with 16 pages each."""
        for memory, used, pages, changed in [
            ([],                               'None',                    '0 full, 0 partial', {}),
            ([0x0000],                         '$0000-$0000 (1 bytes)',   '0 full, 1 partial', {0: '+...............'}),
            ([0xffff],                         '$ffff-$ffff (1 bytes)',   '0 full, 1 partial', {15: '...............+'}),
            ([*range(0x1000, 0x1100), 0x1234], '$1000-$1234 (565 bytes)', '1 full, 1 partial', {1: '#.+.............'}),
        ]:
            with self.subTest(used=used):
                context = Context({})
                context.memory = dict.fromkeys(memory, 0)
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    printMemoryUse(context)
                pageMap = [f'${i:x}000: {changed.get(i, "................")}' for i in range(16)]
                self.assertEqual(output.getvalue().splitlines(), [f'Memory used: {used}', f'Pages used: {pages}', *pageMap])

    def _prgFile(self, directory: str) -> str:
        """Write a .prg file with an rts at $1000, and return its name."""
        prgFile = os.path.join(directory, 'a.prg')
        with open(prgFile, 'wb') as f:
            f.write(bytes([0x00, 0x10, 0x60]))
        return prgFile

    def testCPUOption(self):
        """--cpu chooses the cpu, the 6502 by default, the 65C02, the R65C02 or the W65C02, both when assembling and disassembling."""
        with tempfile.TemporaryDirectory() as directory:
            asmFile, prgFile = os.path.join(directory, 'test.asm'), os.path.join(directory, 'test.prg')
            with open(asmFile, 'w') as f:
                f.write('stz $d020\nrts\n')
            for arguments in [[], ['--cpu', '6502']]:
                with self.subTest(arguments=arguments):
                    self.assertEqual(self._main([asmFile] + arguments)[0], 1) # the 6502 has no stz
            code, output, errors = self._main([asmFile, '-o', prgFile, '--cpu', '65C02'])
            self.assertEqual(code, 0, errors)
            with open(prgFile, 'rb') as f:
                self.assertEqual(f.read(), bytes([0x00, 0x10, 0x9c, 0x20, 0xd0, 0x60]))
            code, output, errors = self._main(['-d', prgFile, '--cpu', '65C02'])
            self.assertEqual(code, 0, errors)
            self.assertIn('.cpu CPU_65C02', [line.strip() for line in output.splitlines()])
            self.assertIn('stz $d020', [line.split(';')[0].strip() for line in output.splitlines()])
            code, output, errors = self._main(['-d', prgFile])
            self.assertEqual(code, 0, errors)
            self.assertNotIn('stz', output)
            self.assertNotIn('.cpu', output)
            with open(asmFile, 'w') as f:
                f.write('rmb3 $12\nrts\n')
            self.assertEqual(self._main([asmFile, '--cpu', '65C02'])[0], 1) # the 65C02 has no rmb3
            code, output, errors = self._main([asmFile, '-o', prgFile, '--cpu', 'R65C02'])
            self.assertEqual(code, 0, errors)
            code, output, errors = self._main(['-d', prgFile, '--cpu', 'R65C02'])
            self.assertEqual(code, 0, errors)
            self.assertIn('.cpu CPU_R65C02', [line.strip() for line in output.splitlines()])
            self.assertIn('rmb3 $12', [line.split(';')[0].strip() for line in output.splitlines()])
            with open(asmFile, 'w') as f:
                f.write('wai\nrts\n')
            self.assertEqual(self._main([asmFile, '--cpu', 'R65C02'])[0], 1) # the R65C02 has no wai
            code, output, errors = self._main([asmFile, '-o', prgFile, '--cpu', 'W65C02'])
            self.assertEqual(code, 0, errors)
            code, output, errors = self._main(['-d', prgFile, '--cpu', 'W65C02'])
            self.assertEqual(code, 0, errors)
            self.assertIn('.cpu CPU_W65C02', [line.strip() for line in output.splitlines()])
            self.assertIn('wai', [line.split(';')[0].strip() for line in output.splitlines()])

    def testDisassembleToFile(self):
        """-d disassembles to the -o file, also with the long option names."""
        with tempfile.TemporaryDirectory() as directory:
            prgFile, asmFile = self._prgFile(directory), os.path.join(directory, 'a.asm')
            for arguments in [['-d', prgFile, '-o', asmFile], ['--disassemble', prgFile, '--output', asmFile]]:
                with self.subTest(arguments=arguments[0]):
                    code, output, errors = self._main(arguments)
                    self.assertEqual(code, 0)
                    with open(asmFile) as f:
                        self.assertEqual(f.read(), disassemble.disassembleFile(prgFile))
                    os.remove(asmFile)

    def testDisassemblePrints(self):
        """Without -o, only the source is printed."""
        with tempfile.TemporaryDirectory() as directory:
            prgFile = self._prgFile(directory)
            code, output, errors = self._main(['-d', prgFile])
            self.assertEqual(code, 0)
            self.assertEqual(output, disassemble.disassembleFile(prgFile))
            self.assertEqual(errors, '')

    def testSourceNotUtf8(self):
        """A source file that is not UTF-8, also when imported, gives an error with its name and line."""
        with tempfile.TemporaryDirectory() as directory:
            badFile, importFile = os.path.join(directory, 'bad.asm'), os.path.join(directory, 'import.asm')
            with open(badFile, 'wb') as f:
                f.write(b'nop\n; caf\xe9\n')
            with open(importFile, 'w') as f:
                f.write('.import "bad.asm"\n')
            for asmFile in [badFile, importFile]:
                with self.subTest(asmFile=asmFile):
                    code, output, errors = self._main([asmFile])
                    self.assertEqual(code, 1)
                    self.assertEqual(errors, f'error: Not valid UTF-8 on line 2: "{badFile}"\n')

    def testDisassembleMissingFile(self):
        """A file that can't be read exits with 1, and an error on stderr."""
        with tempfile.TemporaryDirectory() as directory:
            missingFile = os.path.join(directory, 'missing.prg')
            code, output, errors = self._main(['-d', missingFile, '-o', os.path.join(directory, 'a.asm')])
            self.assertEqual(code, 1)
            self.assertIn(f'error: No such file or directory: "{missingFile}"', errors)

    def testDisassembleInvalidLabels(self):
        """A labels file that can't be used exits with 1, and an error with its name on stderr."""
        with tempfile.TemporaryDirectory() as directory:
            prgFile, labelsFile = self._prgFile(directory), os.path.join(directory, 'labels.py')
            for content, exception in [(b'x = (\n', 'SyntaxError'), (b'x = nope\n', 'NameError'), (b'\xff\n', 'UnicodeDecodeError')]:
                with self.subTest(content=content):
                    with open(labelsFile, 'wb') as f:
                        f.write(content)
                    code, output, errors = self._main(['-d', prgFile, '-l', labelsFile])
                    self.assertEqual(code, 1)
                    self.assertIn(f'error: Invalid labels file ({exception}: ', errors)
                    self.assertIn(f'"{labelsFile}"', errors)

    def testDisassembleMissingLabels(self):
        """A labels file that doesn't exist gives the usual error for a missing file."""
        with tempfile.TemporaryDirectory() as directory:
            labelsFile = os.path.join(directory, 'missing.py')
            code, output, errors = self._main(['-d', self._prgFile(directory), '-l', labelsFile])
            self.assertEqual(code, 1)
            self.assertIn(f'error: No such file or directory: "{labelsFile}"', errors)

    def testDisassembleMissingFolder(self):
        """A file that can't be written exits with 1, and an error on stderr."""
        with tempfile.TemporaryDirectory() as directory:
            missingFolder = os.path.join(directory, 'missing', 'a.asm')
            code, output, errors = self._main(['-d', self._prgFile(directory), '-o', missingFolder])
            self.assertEqual(code, 1)
            self.assertIn(f'error: No such file or directory: "{missingFolder}"', errors)

    def testPackageImports(self):
        """Importing the package keeps its modules inside it, e.g. nopa.cpu, not a top level cpu."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        modules = subprocess.run([sys.executable, '-c', 'import sys, nopa.main; print(*sorted(sys.modules))'],
                                 cwd=root, capture_output=True, text=True, check=True).stdout.split()
        self.assertIn('nopa.cpu', modules)
        self.assertNotIn('cpu', modules)
        self.assertNotIn('assemble', modules)

    def testRunAsModule(self):
        """python -m nopa runs the command line, the same as python -m nopa.main."""
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for module in ['nopa', 'nopa.main']:
            with self.subTest(module=module):
                output = subprocess.run([sys.executable, '-m', module, '--version'], cwd=root, capture_output=True, text=True)
                self.assertEqual((output.returncode, output.stderr), (0, ''))
                self.assertEqual(output.stdout, f'Nop Assembler v{__version__} (c) Morten Perriard 2021-2026\n')

    def testPublicApi(self):
        """The package exports assembleFile, disassembleFile and Context, and its modules stay importable."""
        import nopa
        self.assertEqual(sorted(nopa.__all__), ['Context', 'assembleFile', 'disassembleFile'])
        self.assertIs(nopa.assembleFile, assemble.assembleFile)
        self.assertIs(nopa.disassembleFile, disassemble.disassembleFile)
        self.assertIs(nopa.Context, Context)
        self.assertIs(nopa.disassemble, disassemble) # the module, not the function of the same name


if __name__ == '__main__':
    unittest.main()
