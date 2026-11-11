#! /usr/bin/env python3
"""The versions of Commodore BASIC: their keywords and tokens, and generators for a BASIC program.

Each target chooses the version of its machine, in imports/target/<target>/basic.py.
"""

# The keywords of BASIC 1.0, with tokens from $80, in token order. As in the PET ROM
_BASIC_1_KEYWORDS = (
    'END', 'FOR', 'NEXT', 'DATA', 'INPUT#', 'INPUT', 'DIM', 'READ', 'LET', 'GOTO', 'RUN', 'IF',
    'RESTORE', 'GOSUB', 'RETURN', 'REM', 'STOP', 'ON', 'WAIT', 'LOAD', 'SAVE', 'VERIFY', 'DEF',
    'POKE', 'PRINT#', 'PRINT', 'CONT', 'LIST', 'CLR', 'CMD', 'SYS', 'OPEN', 'CLOSE', 'GET', 'NEW',
    'TAB(', 'TO', 'FN', 'SPC(', 'THEN', 'NOT', 'STEP', '+', '-', '*', '/', '^', 'AND', 'OR', '>',
    '=', '<', 'SGN', 'INT', 'ABS', 'USR', 'FRE', 'POS', 'SQR', 'RND', 'LOG', 'EXP', 'COS', 'SIN',
    'TAN', 'ATN', 'PEEK', 'LEN', 'STR$', 'VAL', 'ASC', 'CHR$', 'LEFT$', 'RIGHT$', 'MID$')

# BASIC 2.0 adds GO, with the token $cb. As in the PET, VIC-20 and C64 ROMs
_BASIC_2_KEYWORDS = _BASIC_1_KEYWORDS + ('GO',)

# BASIC 3.5 adds these keywords, with tokens from $cc. As in the Plus/4 ROM
_BASIC_3_5_KEYWORDS = _BASIC_2_KEYWORDS + (
    'RGR', 'RCLR', 'RLUM', 'JOY', 'RDOT', 'DEC', 'HEX$', 'ERR$', 'INSTR', 'ELSE', 'RESUME', 'TRAP',
    'TRON', 'TROFF', 'SOUND', 'VOL', 'AUTO', 'PUDEF', 'GRAPHIC', 'PAINT', 'CHAR', 'BOX', 'CIRCLE',
    'GSHAPE', 'SSHAPE', 'DRAW', 'LOCATE', 'COLOR', 'SCNCLR', 'SCALE', 'HELP', 'DO', 'LOOP', 'EXIT',
    'DIRECTORY', 'DSAVE', 'DLOAD', 'HEADER', 'SCRATCH', 'COLLECT', 'COPY', 'RENAME', 'BACKUP',
    'DELETE', 'RENUMBER', 'KEY', 'MONITOR', 'USING', 'UNTIL', 'WHILE')

# BASIC 4.0 adds these disk keywords, with tokens from $cc. As in the PET ROM
_BASIC_4_KEYWORDS = _BASIC_2_KEYWORDS + (
    'CONCAT', 'DOPEN', 'DCLOSE', 'RECORD', 'HEADER', 'COLLECT', 'BACKUP', 'COPY', 'APPEND', 'DSAVE',
    'DLOAD', 'CATALOG', 'RENAME', 'SCRATCH', 'DIRECTORY')

# BASIC 4.0+ adds these keywords, with tokens from $db. As in the CBM-II ROMs
_BASIC_4_PLUS_KEYWORDS = _BASIC_4_KEYWORDS + (
    'DCLEAR', 'BANK', 'BLOAD', 'BSAVE', 'KEY', 'DELETE', 'ELSE', 'TRAP', 'RESUME', 'DISPOSE', 'PUDEF',
    'USING', 'ERR$', 'INSTR')

# BASIC 7.0 has the keywords of BASIC 3.5, except RLUM, as $ce is a prefix for two-byte tokens. As in the C128 ROM
_BASIC_7_KEYWORDS = tuple(None if k == 'RLUM' else k for k in _BASIC_3_5_KEYWORDS)

# The keywords of BASIC 7.0 with two-byte tokens: a prefix, and a second byte from $02. None is unused.
# BASIC tries them before the other keywords, in this order, so DOPEN is not DO and PEN. As in the C128 ROM
_BASIC_7_PREFIXED = {
    0xfe: ('BANK', 'FILTER', 'PLAY', 'TEMPO', 'MOVSPR', 'SPRITE', 'SPRCOLOR', 'RREG', 'ENVELOPE', 'SLEEP',
           'CATALOG', 'DOPEN', 'APPEND', 'DCLOSE', 'BSAVE', 'BLOAD', 'RECORD', 'CONCAT', 'DVERIFY', 'DCLEAR',
           'SPRSAV', 'COLLISION', 'BEGIN', 'BEND', 'WINDOW', 'BOOT', 'WIDTH', 'SPRDEF', 'QUIT', 'STASH', None,
           'FETCH', None, 'SWAP', 'OFF', 'FAST', 'SLOW'),
    0xce: ('POT', 'BUMP', 'PEN', 'RSPPOS', 'RSPRITE', 'RSPCOLOR', 'XOR', 'RWINDOW', 'POINTER'),
}

# The symbol names of keywords with other characters than letters, e.g. BASIC_TOKEN_PLUS for +.
# Otherwise $ and ( are left out, e.g. BASIC_TOKEN_CHR for CHR$
_TOKEN_NAMES = {'INPUT#': 'INPUT_FILE', 'PRINT#': 'PRINT_FILE', '+': 'PLUS', '-': 'MINUS', '*': 'MULTIPLY',
                '/': 'DIVIDE', '^': 'POWER', '>': 'GREATER', '=': 'EQUAL', '<': 'LESS'}

BASIC_TOKEN_PI = 0xff # the pi character, in all versions


class Basic:
    """A version of Commodore BASIC: its keywords, which BASIC stores as tokens."""

    def __init__(self, version: str, keywords: tuple, prefixed: dict | None = None):
        """keywords: the keywords with one-byte tokens, from $80, in token order. None is unused.
        prefixed: the keywords with two-byte tokens, {prefix: keywords}, with the second byte from $02.
        BASIC tries them first, in this order.
        """
        self.version = version
        self.keywords = keywords
        self.prefixed = prefixed or {}
        # the bytes of each keyword, in the order BASIC tries them
        self._tokens = [(k, [prefix, 2 + i]) for prefix, ks in self.prefixed.items() for i, k in enumerate(ks) if k]
        self._tokens += [(k, [0x80 + i]) for i, k in enumerate(keywords) if k]
        self._tokens += [('?', [0x80 + keywords.index('PRINT')])] # ? is short for PRINT

    def __repr__(self) -> str:
        return f'Basic({self.version!r})'

    def tokens(self) -> dict:
        """The BASIC_TOKEN_ symbols: the token of each keyword with a one-byte token, and the pi character."""
        tokens = {f'BASIC_TOKEN_{_TOKEN_NAMES.get(k, k.rstrip("$("))}': 0x80 + i for i, k in enumerate(self.keywords) if k}
        return tokens | {'BASIC_TOKEN_PI': BASIC_TOKEN_PI}

    def encode(self, text: str) -> list:
        """The bytes of a BASIC line, as BASIC stores it: keywords become tokens, and the rest stays as text.

        Keywords are not converted in strings, after REM, or in DATA, up to the next ":".
        Raises UnicodeEncodeError for characters that BASIC can't store.
        """
        text = text.upper() # BASIC keywords are in upper case, and so is its text in the default character set
        data: list[int] = []
        index = 0
        inString = False # between two " characters
        literal = None   # REM or DATA, while in its text

        while index < len(text):
            # the keyword at this position, trying them in the order BASIC does, so INPUT# comes before INPUT
            found = None
            if not inString and not literal:
                found = next(((k, t) for k, t in self._tokens if text.startswith(k, index)), None)

            if found:
                # the token replaces the whole keyword
                keyword, token = found
                data += token
                index += len(keyword)
                literal = keyword if keyword in ('REM', 'DATA') else None
            else:
                # any other character is stored as it is. A " starts or ends a string
                inString ^= text[index] == '"'
                # a ":" ends a DATA statement, unless it is in a string. REM always lasts to the end of the line
                if literal == 'DATA' and text[index] == ':' and not inString:
                    literal = None
                if text[index] == 'Π': # the pi character, π, in upper case
                    data.append(BASIC_TOKEN_PI)
                else:
                    data.append(text[index].encode('ascii')[0])
                index += 1

        return data

    def symbols(self) -> dict:
        """The symbols of a target with this version: the BASIC_TOKEN_ values, and the generators."""

        def basicLine(lineNumber, text):
            """A BASIC line, with keywords as tokens, e.g. "POKE 53280,0:SYS 2061"."""
            data = self.encode(text) + [0]
            return f"""
            .word _ + 2 + 2 + {len(data)}
            .word {lineNumber}
            .byte {', '.join(map(str, data))}
            """

        def basicSys(lineNumber, address):
            """A BASIC line with a SYS to the address, the same as basicLine(lineNumber, f"SYS{address}"). Kept for compatibility."""
            return basicLine(lineNumber, f"SYS{address}")

        return self.tokens() | {'basicStart': _basicStart, 'basicLine': basicLine, 'basicSys': basicSys, 'basicEnd': _basicEnd}


def _basicStart():
    """Set the address to the start of the BASIC program, BASIC_START_ADDRESS, which each target defines."""
    return """
    .org BASIC_START_ADDRESS
    """


def _basicEnd():
    """The end of the BASIC program."""
    return """
    .word 0
    """


BASIC_1      = Basic('1.0', _BASIC_1_KEYWORDS)
BASIC_2      = Basic('2.0', _BASIC_2_KEYWORDS)
BASIC_3_5    = Basic('3.5', _BASIC_3_5_KEYWORDS)
BASIC_4      = Basic('4.0', _BASIC_4_KEYWORDS)
BASIC_4_PLUS = Basic('4.0+', _BASIC_4_PLUS_KEYWORDS)
BASIC_7      = Basic('7.0', _BASIC_7_KEYWORDS, _BASIC_7_PREFIXED)
