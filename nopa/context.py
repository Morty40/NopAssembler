#! /usr/bin/env python3
"""The assembler state: symbols, memory, messages and the current line."""

import math
import types

from . import cpu
from . import text


class Namespace(types.ModuleType):
    """The module that .py files are imported into with .import "file.py", "namespace".

    A type of its own, so a symbol can't change between a namespace and another module,
    e.g. one imported by Python code.
    """


def namespacedName(name: str, namespace: str) -> str:
    """The name a symbol defined in a namespace gets, e.g. draw in spr is spr_draw, and a constant
    keeps its capitals, so SPEED is SPR_SPEED. Without a namespace, '', the name is unchanged,
    and so is _, the current address."""
    if not namespace or name == '_':
        return name
    return f'{namespace.upper()}_{name}' if name.isupper() else f'{namespace}_{name}'


class NamespaceSymbols(dict):
    """The symbols as the code in a namespace sees them: its own names first, e.g. draw is spr_draw
    if that is defined, then those of the outer namespaces, e.g. spr_util_draw before spr_draw,
    and else the global ones. A name it defines gets the innermost namespace.

    Used as the globals of eval() and exec(), which then look names up here, also in lambdas and
    functions. It copies nothing: its own dict only holds the __builtins__ that eval() adds.

    The global statement isn't supported in a namespace: Python stores a name declared global
    straight into this dict, without __setitem__, so the symbols never get it, and reading it
    back fails. Code in a namespace keeps state in a container instead, e.g. counts = [0] and
    counts[0] += 1 in a function.
    """

    def __init__(self, symbols: dict, namespaces: tuple[str, ...]):
        super().__init__()
        self.symbols = symbols
        self.namespaces = namespaces # outermost first, e.g. ('spr', 'util')

    def candidates(self, name: str) -> list[str]:
        """The symbols a name can be looked up as, in order, e.g. spr_util_draw, spr_draw and draw."""
        prefixes = ['_'.join(self.namespaces[:depth]) for depth in range(len(self.namespaces), 0, -1)] # innermost first
        return [namespacedName(name, prefix) for prefix in prefixes] + [name]

    def resolve(self, name: str) -> str:
        """The symbol a name is looked up as: the first candidate that is defined, else the name itself."""
        return next((candidate for candidate in self.candidates(name) if candidate in self.symbols), name)

    def __getitem__(self, name: str):
        symbol = self.resolve(name)
        if symbol == 'ref': # the built-in ref(), with the label looked up in this namespace, wherever it is called from
            return lambda label: self.symbols['ref'](self.resolve(label))
        return self.symbols[symbol]

    def __contains__(self, name) -> bool:
        """True if the name is defined as it is looked up, for name in globals() in Python code."""
        return self.resolve(name) in self.symbols

    def get(self, name, default=None):
        """The value of the name as it is looked up, or the default, for globals().get() in Python code."""
        return self.symbols.get(self.resolve(name), default)

    def __setitem__(self, name: str, value):
        self.symbols[namespacedName(name, '_'.join(self.namespaces))] = value


class Context:
    """The state of one assemble pass.

    The read pointer stack has a (fileName, lineIndex) for each file
    being assembled. The top is the current line, and an imported file
    or generator is pushed on top of the file that uses it. Each also has
    the namespaces it is in, outermost first, that the names it defines
    are prefixed with, e.g. spr_util_draw for ('spr', 'util').
    """

    def __init__(self, symbols: dict):
        """Create the state for a pass. The symbols are shared by all passes."""
        self.readPointerStack: list[tuple[str, int]] = []
        self.namespaceStack: list[tuple[str, ...]] = [] # the namespaces of each read pointer, () for none

        # math, and ord/chr in the current text encoding, for expressions
        symbols.update(math.__dict__)
        symbols['ord'] = lambda char: text.ord(char, self.encoding)
        symbols['chr'] = lambda value: text.chr(value, self.encoding)
        symbols['ref'] = lambda label: label in self.lastReferences # in a namespace, NamespaceSymbols looks the label up first
        symbols['zp'] = self.zp
        self.symbols = symbols
        self.labels: set[str] = set() # labels defined in this pass, to find duplicates
        self.memory: dict[int, int] = {} # address: byte
        self.printed: list[object] = [] # from .print, shown after the last pass
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.blockStack: list[tuple] = [] # per open .repeat, .for or .if: (kind, ...), see directives.py
        self.zpAddress = 2 # the next free zero page address, for zp(): $0 and $1 are reserved
        self.sections: dict[str, int] = {} # section name: the address where it continues
        self.currentSection: str | None = None # the name given to the last .section
        self.generatorCounts: dict[str, int] = {} # generator name: calls, gives each call its own local label scope
        self.namespaces: dict[str, Namespace] = {} # namespace, e.g. util or spr_util: its module, shared by the .py files imported into it in this pass
        self.breakpoints: list[tuple[int, str | None]] = [] # (address, VICE condition or None) for each .break
        self.path = '' # folder of the main source file, for .import and .binary
        self.encoding: dict[str, int] = text.ENCODING_SCREEN_UPPER
        self.cpu: cpu.CPU = cpu.CPU_6502 # the instructions
        self.references: set[str] = set() # the names used by the Python code and expressions in this pass
        self.lastReferences: set[str] = set() # the same from the last pass, for ref() and .optional

    def noteReferences(self, code):
        """Note the names used by compiled Python code, including the functions in it,
        as the symbols they are looked up as in the current namespace, e.g. spr_draw for draw.

        A name that isn't defined yet is noted as all the symbols it could be, so an optional block
        that defines it is assembled, and the next pass notes just the one it is.
        """
        view = NamespaceSymbols(self.symbols, self.currentNamespaces()) if self.currentNamespaces() else None
        for name in code.co_names:
            if view is not None:
                candidates = view.candidates(name)
                defined = [candidate for candidate in candidates if candidate in self.symbols]
                self.references.update(defined[:1] or candidates)
            else:
                self.references.add(name)
        for constant in code.co_consts:
            if isinstance(constant, types.CodeType):
                self.noteReferences(constant)

    def zp(self, size: int) -> int:
        """Allocate size bytes in zero page, and return the address of the first, e.g. counter = zp(1)."""
        if type(size) is not int:
            raise TypeError(f'Zero page size must be an int, not {type(size).__name__}')
        if size < 1:
            raise ValueError('Zero page size must be positive')
        if self.zpAddress + size > 0x100:
            raise ValueError(f'Not enough zero page left: {size} needed, {0x100 - self.zpAddress} left')
        address = self.zpAddress
        self.zpAddress += size
        return address

    def setSymbol(self, name: str, value) -> bool:
        """Set a symbol, which keeps its type, e.g. an int can't become a str.

        Returns False, and keeps the old value, if the type would change.
        """
        if name in self.symbols and type(self.symbols[name]) != type(value):
            oldType, newType = type(self.symbols[name]).__name__, type(value).__name__
            self.reportError(f'Symbol "{name}" cannot change type from {oldType} to {newType}')
            return False
        self.symbols[name] = value
        return True

    def store(self, value: int):
        """Store a byte at the current address, and advance the address."""
        currentLocation = self.symbols['_']

        if currentLocation >= 0 and currentLocation <= 0xffff:

            if currentLocation in self.memory:
                oldValue = self.memory[currentLocation]
                self.reportWarning(f'${currentLocation:04x} is overwritten (${oldValue:02x} to ${value:02x})')

            # store value in memory, and advance to next memory location
            self.memory[currentLocation] = value
            self.symbols['_'] += 1

        else:
            self.reportError(f'Destination memory address out of range: ${currentLocation:x}')

    def storeWord(self, value: int):
        """Store a 16-bit word, low byte first."""
        self.store(value & 0xff)
        self.store((value >> 8) & 0xff)

    def readPointer(self):
        """Return the current (fileName, lineIndex), or None when done."""
        return self.readPointerStack[-1] if self.readPointerStack else None

    def jumpReadPointer(self, readPointer: tuple):
        """Continue from another line. Used by .end to loop back."""
        if self.readPointerStack:
            self.readPointerStack[-1] = readPointer

    def pushReadPointer(self, readPointer: tuple, namespace: str | None = None):
        """Start assembling another file, on top of the current one, in the same namespaces,
        and in the namespace inside them, if given."""
        namespaces = self.currentNamespaces() if namespace is None else self.currentNamespaces() + (namespace,)
        self.namespaceStack.append(namespaces)
        self.readPointerStack.append(readPointer)

    def popReadPointer(self):
        """Finish the current file, and return its read pointer."""
        if self.namespaceStack:
            self.namespaceStack.pop()
        return self.readPointerStack.pop() if self.readPointerStack else None

    def currentNamespaces(self) -> tuple[str, ...]:
        """The namespaces of the current file, outermost first, () for none."""
        return self.namespaceStack[-1] if self.namespaceStack else ()

    def namespace(self) -> str:
        """The prefix of the names the current file defines, e.g. spr_util, '' for none."""
        return '_'.join(self.currentNamespaces())

    def namespacedName(self, name: str) -> str:
        """The name a symbol defined in the current namespace gets, see namespacedName()."""
        return namespacedName(name, self.namespace())

    def namespaceSymbols(self) -> dict:
        """The symbols as the code in the current namespace sees them, for eval() and exec()."""
        return NamespaceSymbols(self.symbols, self.currentNamespaces()) if self.currentNamespaces() else self.symbols

    def advanceReadPointer(self):
        """Move to the next line, and return the new read pointer."""
        if self.readPointerStack:
            fileName, lineIndex = self.readPointerStack[-1]
            self.readPointerStack[-1] = (fileName, lineIndex + 1)
            return self.readPointerStack[-1]

    def _formattedReadPointer(self):
        """Return the current position as 'file:line: ', for messages, as in gcc."""
        rp = self.readPointer()
        return f'{rp[0]}:{rp[1]+1}: ' if rp else ''

    def reportWarning(self, text: str):
        """Add a warning, at the current file and line."""
        rp = self._formattedReadPointer()
        self.warnings.append(f'{rp}warning: {text}')

    def reportError(self, text: str):
        """Add an error, at the current file and line."""
        rp = self._formattedReadPointer()
        self.errors.append(f'{rp}error: {text}')
