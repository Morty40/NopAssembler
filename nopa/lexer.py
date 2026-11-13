#! /usr/bin/env python3
"""The lexer: splits source code into tokens, one line at a time."""

import errno
import keyword
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


def isValidGlobalSymbolName(name: str) -> bool:
    """A name the source can use for a global symbol: an identifier that isn't a Python keyword,
    and doesn't start with _, as translateLocalLabels() would make it a local label."""
    return name.isidentifier() and not keyword.iskeyword(name) and not name.startswith('_')


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
