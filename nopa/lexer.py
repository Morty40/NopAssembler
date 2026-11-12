#! /usr/bin/env python3
"""The lexer: splits source code into tokens, one line at a time."""

import errno
import os
import re
import textwrap
from dataclasses import dataclass
from typing import Iterator

from . import cpu


# the tokens of a line, in the order they are tried, with the longest operators first
_TOKEN = re.compile(r'''
    ;.*                                         # comment
  | [A-Za-z]*"(?:\\.|[^"\\])*"                  # strings, with any prefix
  | [A-Za-z]*'(?:\\.|[^'\\])*'
  | \$\w*                                       # hex number
  | %[01]+\b                                    # binary number, or modulo and a number, see tokenize()
  | \d[\w.]*(?:(?<=[eE])[-+]\d+)?               # number, with an optional signed exponent
  | \w+                                         # name
  | <<|>>|<=|>=|==|!=|\*\*|//|:=                 # operators of two characters
  | \S                                          # anything else, including an unmatched quote
''', re.VERBOSE)


_KEYWORDS = ('if', 'else', 'or', 'not', 'in', 'is') # Python keywords that an operand follows


@dataclass
class Token:
    """A word or symbol from the source, e.g. a mnemonic or a number."""
    string: str
    fileName: str = ''
    lineNumber: int = 0

    def __repr__(self):
        """The token with its file and line, for debugging."""
        s = self.string.replace('\n', '\\n')
        return f'{s} ({self.fileName}:{self.lineNumber})'


def _fixPrefix(word: str) -> str:
    """Convert hex and binary prefixes $ and % to 0x and 0b, and all strings to f-strings."""
    if word.startswith('$'):
        word = '0x' + word[1:]
    elif re.fullmatch(r'%[01]+', word):
        word = '0b' + word[1:]
    elif word.startswith('"') and word.endswith('"'):
        word = 'f' + word
    return word


def translateLocalLabels(tokens: list, lastLabel: str='') -> list:
    """Prefix local labels (starting with _, and not all capitals) with the last global label."""
    newTokens = []
    for lineTokens in splitByNewline(tokens):

        if len(lineTokens) >= 2 and not lineTokens[0].string.startswith('_') and lineTokens[1].string == ':':
            lastLabel = lineTokens[0].string

        for token in lineTokens:
            if len(token.string) > 1 and token.string.startswith('_') and not token.string.isupper():
                token.string = lastLabel + token.string
            newTokens.append(token)

        newTokens.append(Token('\n'))

    return newTokens


def definedNames(tokens: list) -> tuple[set, set]:
    """The names the tokens define, labels and assigned names other than _, and the namespaces of their .import lines."""
    lines = list(splitByNewline(tokens))
    names = {line[0].string for line in lines if len(line) >= 2 and line[1].string in (':', '=') and line[0].string != '_'}
    namespaces = {line[4].string.lstrip('fFrRbBuU')[1:-1] for line in lines # the text of the string, e.g. spr
                  if len(line) == 5 and [t.string for t in line[:2]] == ['.', 'import']}
    return names, namespaces


def namespaceNames(fileName: str, folder: str) -> tuple[set, set]:
    """The names a namespace defines, as definedNames: in the file, and in the files it imports without a namespace,
    whose paths are relative to the folder. They all share the namespace, so they use each other's names as they are."""
    names: set[str] = set()
    namespaces: set[str] = set()
    files = [fileName]
    for name in files: # grows with the files they import
        tokens = tokenizeFile(name)
        fileNames, fileNamespaces = definedNames(tokens)
        names |= fileNames
        namespaces |= fileNamespaces
        for line in splitByNewline(tokens):
            if len(line) == 3 and [t.string for t in line[:2]] == ['.', 'import']:
                imported = os.path.join(folder, line[2].string.lstrip('fFrRbBuU')[1:-1])
                if not imported.endswith('.py') and os.path.isfile(imported) and imported not in files:
                    files.append(imported)
    return names, namespaces


def prefixNames(tokens: list, prefix: str, defined: tuple[set, set] | None = None) -> list:
    """Prefix the names the tokens define, where they are defined and used: util_draw, or UTIL_SPEED in all capitals.

    The names are the labels and the assigned names, those of definedNames, or the given (names, namespaces) of all
    the files in a namespace. Names of a namespace the tokens import, such as spr_draw after .import "sprites.asm", "spr",
    and the namespace itself, are prefixed too. Names in {} of a string are prefixed, but not a name after a dot,
    a keyword argument, the statement of a line, or _.
    """
    lines = list(splitByNewline(tokens))
    names, namespaces = defined or definedNames(tokens)

    def renamed(name: str) -> str:
        """The name with the prefix, if the tokens define it or import its namespace."""
        if name in names or any(name == n or name.startswith((n + '_', n.upper() + '_')) for n in namespaces):
            return f'{prefix.upper()}_{name}' if name.isupper() else f'{prefix}_{name}'
        return name

    def renamedInBraces(match) -> str:
        """The expression in {} of a string, with its names prefixed."""
        return '{' + re.sub(r'(?<![\w.])[A-Za-z_]\w*', lambda m: renamed(m.group()), match.group(1)) + '}'

    for line in lines:
        statement = 2 if len(line) >= 2 and line[1].string == ':' else 0 # the mnemonic or directive, after a label
        depth = 0
        for i, token in enumerate(line):
            before = line[i - 1].string if i > 0 else ''
            after = line[i + 1].string if i + 1 < len(line) else ''
            if token.string in ('(', '[', '{'):
                depth += 1
            elif token.string in (')', ']', '}'):
                depth -= 1
            elif token.string.startswith('f"'):
                token.string = re.sub(r'\{([^{}]*)\}', renamedInBraces, token.string)
            elif (token.string.isidentifier() and before != '.' and not (depth > 0 and after == '=')
                  and not (i == statement and after not in (':', '='))):
                token.string = renamed(token.string)
    return tokens


def join(tokens: list) -> str:
    """Join tokens into an expression, with a space between adjacent words, e.g. "1 if x else 2"."""
    s = ''
    for t in tokens:
        if re.fullmatch(r'\w\w', s[-1:] + t.string[:1]):
            s += ' '
        s += t.string
    return s


def splitByComma(tokens: list) -> list:
    """Split tokens at the commas that are not inside brackets, e.g. i<len([1, 2])."""
    parts: list[list[Token]] = [[]]
    depth = 0
    for token in tokens:
        if token.string in ('(', '[', '{'):
            depth += 1
        elif token.string in (')', ']', '}'):
            depth -= 1
        if token.string == ',' and depth == 0:
            parts.append([])
        else:
            parts[-1].append(token)
    return parts


def tokenize(text: str, fileName: str='') -> list:
    """Split source code into tokens, with a newline token after each line.

    Comments are removed, $ and % become 0x and 0b, and strings become
    f-strings, so the tokens form valid Python expressions. A block of
    Python code, from .python to .end, becomes one .python line with the code as a
    string, followed by empty lines, so the line numbers stay the same.
    """
    tokens = []

    pythonBlock: list[str] | None = None # the lines of a .python block, while they are collected
    for line in text.splitlines():
        if pythonBlock is not None:
            if re.fullmatch(r'\s*\.end\s*(;.*)?', line): # the end of the .python block
                code = textwrap.dedent('\n'.join(pythonBlock))
                tokens.append(Token(repr(code), fileName))
                tokens += [Token('\n') for _ in range(len(pythonBlock) + 2)] # .python, the code, and .end
                pythonBlock = None
            else:
                pythonBlock.append(line)
            continue

        words = [word for word in _TOKEN.findall(line) if not word.startswith(';')]
        if '"' in words or "'" in words: # no closing quotation
            words = [line] # one token, reported as invalid syntax when assembled

        if words[:2] == ['.', 'python'] and len(words) > 2: # Python code is only allowed in a block
            words = [line] # one token, reported as invalid syntax when assembled
        if words == ['.', 'python']: # a block of Python code follows, up to .end
            tokens += [Token('.', fileName), Token('python', fileName)]
            pythonBlock = []
            continue

        prev = ['', ''] # previous two tokens, to tell modulo from binary prefix
        for token in words:
            # % is modulo after a number, name or closing bracket (7 % 4), and
            # otherwise a binary prefix (%101), e.g. after a directive or mnemonic
            afterOperand = (re.search(r'[\w)\]}"\']$', prev[1]) and prev[1] not in _KEYWORDS
                            and prev[0] != '.' and not cpu.isMnemonic(prev[1]))
            if not (token.startswith('%') and afterOperand):
                token = _fixPrefix(token)
            tokens.append(Token(token, fileName))
            prev = [prev[1], token]
        tokens.append(Token('\n'))
    if pythonBlock is not None: # no .end, so the .python line is reported as an invalid directive
        tokens += [Token('\n') for _ in range(len(pythonBlock) + 1)]

    return tokens


def tokenizeFile(fileName: str) -> list:
    """Tokenize a source file, and translate its local labels. Raises OSError if the file can't be read."""
    try:
        with open(fileName, 'r', encoding='utf-8') as f:
            text = f.read()
    except UnicodeDecodeError as exception:
        line = exception.object.count(b'\n', 0, exception.start) + 1
        raise OSError(errno.EILSEQ, f'Not valid UTF-8 on line {line}', fileName)

    tokens = tokenize(text, fileName)
    tokens = translateLocalLabels(tokens)

    return tokens


def splitByNewline(tokens: list) -> Iterator[list]:
    """A generator that splits a list of tokens by newlines."""
    indices = [i for i, token in enumerate(tokens) if token.string=='\n']
    for start, end in zip([-1, *indices], [*indices, len(tokens)]):
        yield tokens[start+1:end]
