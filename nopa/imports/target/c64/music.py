"""SID music files: reads the header and music data of PSID and RSID files, for @importMusic."""

# named with an underscore, as all names in this file become symbols when assembling
import os as _os
import struct as _struct
from dataclasses import dataclass as _dataclass, field as _field


_HEADER = '>4sHHHHHHHL32s32s32s' # all versions: $76 bytes
_HEADER_V2 = '>HBBBB'            # version 2 and later: flags, startPage, pageLength, secondSIDAddress, thirdSIDAddress

_CLOCKS = ['unknown', 'PAL', 'NTSC', 'PAL and NTSC']
_SID_MODELS = ['unknown', 'MOS6581', 'MOS8580', 'MOS6581 and MOS8580']


@_dataclass
class _Music:
    """The music data from a SID file, the addresses to load, init and play it, and the other header fields.

    Supports PSID versions 1 to 4, and RSID versions 2 to 4.
    """
    loadAddress: int
    initAddress: int # the load address if 0 in the file, except for a BASIC tune
    playAddress: int # 0 if the init routine installs its own interrupt handler
    data: bytes
    magicId: str = 'PSID' # or 'RSID', for tunes that need a real C64 environment
    version: int = 2
    songs: int = 1
    startSong: int = 1 # 1 is the first song
    speed: int = 0 # see usesCiaTimer()
    name: str = ''
    author: str = ''
    released: str = ''
    flags: int = 0 # version 2 and later, see the properties below
    startPage: int = 0 # free memory for relocation, in pages: 0 is clean, $ff is none
    pageLength: int = 0
    sidAddresses: list = _field(default_factory=lambda: [0xd400]) # with a second and third SID in version 3 and 4

    @property
    def isBasic(self) -> bool:
        """RSID only: the music is a BASIC program, to be started with RUN."""
        return self.magicId == 'RSID' and bool(self.flags & 0b10)

    @property
    def isPlaySidSpecific(self) -> bool:
        """PSID only: the music uses PlaySID samples, so needs a PlaySID compatible player."""
        return self.magicId == 'PSID' and bool(self.flags & 0b10)

    @property
    def clock(self) -> str:
        """The video standard: 'unknown', 'PAL', 'NTSC' or 'PAL and NTSC'."""
        return _CLOCKS[self.flags >> 2 & 0b11]

    @property
    def sidModels(self) -> list:
        """The model of each SID: 'unknown', 'MOS6581', 'MOS8580' or 'MOS6581 and MOS8580'."""
        return [_SID_MODELS[self.flags >> shift & 0b11] for shift in [4, 6, 8][:len(self.sidAddresses)]]

    def usesCiaTimer(self, song: int) -> bool:
        """True if the song, from 1, is played by a CIA timer, and False for the vertical blank interrupt."""
        return bool(self.speed >> min(song - 1, 31) & 1) # songs 32 and later share bit 31

    @classmethod
    def _parse(cls, fileData: bytes) -> '_Music':
        """Parse the contents of a SID file. Raises ValueError if it is not valid, or can't be assembled."""
        def _string(value: bytes) -> str:
            """A Latin-1 string field, padded with zeros, or filling all 32 bytes."""
            return value.split(b'\0')[0].decode('latin-1')

        def _sidAddress(value: int):
            """The address of an extra SID from its header byte, $xy for $dxy0, or None if not a valid address."""
            if value % 2 == 0 and (0x42 <= value <= 0x7e or 0xe0 <= value <= 0xfe):
                return 0xd000 | value << 4
            return None

        if len(fileData) < _struct.calcsize(_HEADER):
            raise ValueError('the header is too short')
        (magicId, version, dataOffset, loadAddress, initAddress, playAddress,
         songs, startSong, speed, name, author, released) = _struct.unpack_from(_HEADER, fileData)

        if magicId not in [b'PSID', b'RSID']:
            raise ValueError('not PSID or RSID')
        magicId = magicId.decode('ascii')
        if not (1 if magicId == 'PSID' else 2) <= version <= 4:
            raise ValueError(f'unsupported {magicId} version {version}')

        headerSize = _struct.calcsize(_HEADER) + (_struct.calcsize(_HEADER_V2) if version >= 2 else 0)
        if not headerSize <= dataOffset <= len(fileData):
            raise ValueError(f'the data offset ${dataOffset:x} is not after the header, or is past the end of the file')

        flags, startPage, pageLength, sidAddresses = 0, 0, 0, [0xd400]
        if version >= 2:
            flags, startPage, pageLength, secondSid, thirdSid = _struct.unpack_from(_HEADER_V2, fileData, _struct.calcsize(_HEADER))
            extraSids = [secondSid] if version == 3 else [secondSid, thirdSid] if version == 4 else []
            sidAddresses += [address for address in map(_sidAddress, extraSids) if address is not None]

        if flags & 0b01:
            raise ValueError('Compute!\'s Sidplayer MUS data needs a separate player, and is not supported')
        if magicId == 'RSID':
            if loadAddress != 0:
                raise ValueError('the RSID load address must be 0, with the load address in the data')
            if playAddress != 0:
                raise ValueError('the RSID play address must be 0')
            if speed != 0:
                raise ValueError('the RSID speed must be 0')

        # a load address of 0 means the first two bytes of the data are the load address (lo, hi)
        data = fileData[dataOffset:]
        if loadAddress == 0:
            loadAddress = int.from_bytes(data[:2], 'little')
            data = data[2:]
        if not data:
            raise ValueError('no music data')
        if loadAddress + len(data) > 0x10000:
            raise ValueError(f'the music data from ${loadAddress:04x} goes past $ffff')

        music = cls(loadAddress, initAddress, playAddress, data, magicId, version, songs, startSong, speed,
                    _string(name), _string(author), _string(released), flags, startPage, pageLength, sidAddresses)
        if music.initAddress == 0 and not music.isBasic:
            music.initAddress = loadAddress
        return music

    @classmethod
    def load(cls, fileName: str) -> '_Music':
        """Load a SID file, PSID or RSID, without its header. The path is relative to the folder of the main source file.

        Raises ValueError if the file is not found or not valid.
        """
        try:
            with open(_os.path.join(SOURCE_FOLDER, fileName), 'rb') as f:
                fileData = f.read()
        except FileNotFoundError:
            raise ValueError(f'File not found: "{fileName}"')
        try:
            return cls._parse(fileData)
        except ValueError as exception:
            raise ValueError(f'Not a valid sid file: "{fileName}": {exception}')


def importMusic(fileName: str, prefix: str) -> str:
    """Store the music from a SID file, and define prefix_LOAD, prefix_INIT and prefix_PLAY."""
    music = _Music.load(fileName)
    size = _os.path.getsize(_os.path.join(SOURCE_FOLDER, fileName))
    return f"""
    {prefix}_LOAD = {music.loadAddress}
    {prefix}_INIT = {music.initAddress}
    {prefix}_PLAY = {music.playAddress}
    .binary "{fileName}", {size - len(music.data)}
    """
