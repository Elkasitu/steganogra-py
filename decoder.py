import math
import numpy as np
import pygame
import zlib

from collections import defaultdict


class PNGChunk:

    def __init__(self, _len, _type, data, crc):
        self._internal_counter = 0
        self.len = _len
        self.type = _type
        # critical or ancilliary
        self.critical = _type[0].isupper()
        # public or private
        self.public = _type[1].isupper()
        # adheres to PNG standard or not
        self.standard = _type[2].isupper()
        # safe to copy if modified or not
        self.safe = _type[3].isupper()
        self.data = data
        self.crc = crc

    def get_data(self, i=1):
        c = self._internal_counter
        if i == 1:
            res = self.data[c]
            self._internal_counter += 1
        else:
            res = self.data[c:c + i]
            self._internal_counter += i
        return res


class PNGDecoder:

    def __init__(self, buffer):
        self._internal_counter = 0
        self._buffer = buffer
        self.image = None

    def next(self, i=1):
        c = self._internal_counter
        if i == 1:
            res = self._buffer[c]
            self._internal_counter += 1
        else:
            res = self._buffer[c:c + i]
            self._internal_counter += i
        return res

    def _get_header(self):
        # PNG format has an 8-byte header
        # should be 0x89 0x50 0x4e 0x47 0x0d 0x0a 0x1a 0x0a
        return self.next(8)

    def get_next_chunk(self):
        c_len = int.from_bytes(self.next(4), 'big')
        c_type = self.next(4).decode()
        assert c_len < (len(self._buffer) - self._internal_counter), \
            "Buffer overflow: Length of chunk is %d but only %d bytes remain in buffer" % (
                    c_len, len(self._buffer) - self._internal_counter
                )
        c_data = self.next(c_len)
        c_crc = self.next(4)
        return PNGChunk(c_len, c_type, c_data, c_crc)

    def _perform_checks(self):
        if self.image.color_type == 3:
            assert self.image.palette, "Indexed color PNG images require the PLTE chunk"
        if self.image.color_type in (0, 4):
            assert not self.image.palette, "Grayscale PNG images forbid the PLTE chunk"

    def _parse_chunk(self, chunk):
        if chunk.type == 'IHDR':
            w = int.from_bytes(chunk.get_data(4), 'big')
            h = int.from_bytes(chunk.get_data(4), 'big')
            d = int(chunk.get_data())
            ct = int(chunk.get_data())
            cm = int(chunk.get_data())
            fm = int(chunk.get_data())
            im = int(chunk.get_data())
            self.image = PNGImage(w, h, d, ct, cm, fm, im)
        elif chunk.type == 'PLTE':
            self.image.palette = chunk.data
        elif chunk.type == 'IDAT':
            self._perform_checks()
            self.image.data += chunk.data
        elif chunk.type == 'IEND':
            return False
        return True

    def decode(self):
        h = self._get_header()
        assert h == b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a', "File is not of PNG format"
        first = self.get_next_chunk()
        parsed = self._parse_chunk(first)

        while parsed:
            chunk = self.get_next_chunk()
            parsed = self._parse_chunk(chunk)

    def inflate(self):
        self.image.data = zlib.decompress(self.image.data)

    def _paeth_predictor(self, a, b, c):
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)

        if pa <= pb and pa <= pc:
            return a
        elif pb <= pc:
            return b
        return c

    def defilter(self):
        buffer = b''
        for y, scanline in enumerate(list(self.image.scanlines.values())):
            filter_type = scanline[0]
            scanline = scanline[1:]
            if filter_type == 0:
                # do nothing except remove the filter_type byte
                defiltered = scanline
            elif filter_type == 1:
                # sub filtering
                defiltered = b''
                for x, byte in enumerate(scanline):
                    if x - self.image.bpp < 0:
                        sub = 0
                    else:
                        sub = defiltered[x - self.image.bpp]
                    defiltered += hex((byte + sub) % 256)
            elif filter_type == 2:
                # up filtering
                defiltered = b''
                for x, byte in enumerate(scanline):
                    if y == 0:
                        up = 0
                    else:
                        up = scanlines[y - 1][x]
                    defiltered += hex((byte + up) % 256)
            elif filter_type == 3:
                # average filtering
                defiltered = b''
                for x, byte in enumerate(scanline):
                    if x - self.image.bpp < 0:
                        sub = 0
                    else:
                        sub = defiltered[x - self.image.bpp]
                    if y == 0:
                        up = 0
                    else:
                        up = scanlines[y - 1][x]
                    defiltered += hex((byte + math.floor((sub + up) / 2)) % 256)
            elif filter_type == 4:
                # paeth filtering
                defiltered = b''
                for x, byte in enumerate(scanline):
                    if x - self.image.bpp < 0:
                        sub = 0
                        diag = 0
                    else:
                        sub = defiltered[x - self.image.bpp]
                        if y == 0:
                            up = 0
                            diag = 0
                        else:
                            up = scanlines[y - 1][x]
                            diag = scanlines[y - 1][x - self.image.bpp]
                    defiltered += hex((byte + self._paeth_predictor(sub, up, diag)) % 256)
            else:
                defiltered = b''
                print("Unknown filter type for scanline %d" % y)
            buffer += defiltered
        self.image.data = buffer


class PNGImage:

    TYPE_MULTIPLIER = {
            0: 1, # grayscale
            2: 3, # truecolor
            3: 1, # indexed/palette
            4: 2, # grayscale + alpha
            6: 3, # truecolor + alpha
        }

    def __init__(self, width, height, depth, color_type, cmp_method, filter_method, int_method):
        self.width = width
        self.height = height
        self.depth = depth
        self.color_type = color_type
        self.cmp_method = cmp_method
        self.filter_method = filter_method
        self.int_method = int_method
        self.palette = None
        self.data = b''
        self._bitmap = []
        self._scanlines = []
        # depth is in bits but bytes are needed, 1/8 = 1, 2/8 = 1, 4/8 = 1, 8/8 = 1, 16/8 = 2
        self.bpp = PNGImage.TYPE_MULTIPLIER[self.color_type] * math.ceil((self.depth / 8))

    @property
    def bitmap(self):
        while len(self._bitmap) < self.height:
            buffer = []
            i = 0
            while len(buffer) < self.width:
                # TODO: truecolor-specific
                r, g, b = self.data[i:i + 3]
                buffer.append(np.array([r, g, b]))
                i += 3
            self._bitmap.append(np.array(buffer))
        return np.array(self._bitmap)

    @property
    def interlaced(self):
        start_x = {0: 0, 1: 4, 2: 0, 3: 2, 4: 0, 5: 1, 6: 0}
        start_y = {0: 0, 1: 0, 2: 4, 3: 0, 4: 2, 5: 0, 6: 1}
        delta_x = {0: 8, 1: 8, 2: 4, 3: 4, 4: 2, 5: 2, 6: 1}
        delta_y = {0: 8, 1: 8, 2: 8, 3: 4, 4: 4, 5: 2, 6: 2}

        _pass = 0
        map = [[0] * self.width] * self.height
        while _pass < 7:
            y = start_y[_pass]
            while y < self.height:
                x = start_x[_pass]
                max_x = 0
                while x < self.width:
                    # XXX: truecolor-specific
                    normalized = ((y * max_x) + (x * 3))
                    r, g, b = self.data[normalized:normalized + 3]
                    map[y][x] = np.array([r, g, b])
                    x += delta_x[_pass]
                max_x += (x / delta_x[_pass])
                y += delta_y[_pass]
            _pass += 1
        return np.array([np.array(row for row in map)])

    @property
    def scanlines(self):
        x_sub = self.width / 8
        y_sub = self.width / 8
        scanlines = defaultdict(bytes)
        bpss = [
            1 * x_sub * self.bpp,
            1 * x_sub * self.bpp,
            2 * x_sub * self.bpp,
            2 * x_sub * self.bpp,
            4 * x_sub * self.bpp,
            4 * x_sub * self.bpp,
            8 * x_sub * self.bpp,
        ]

        for i, bps in enumerate(bpss):
            start = 0
            while start < y_sub:
                # take into account the filter_type byte
                end = start + int(bps) + 1
                scanlines[i] += self.data[start:end]
                start = end
        return scanlines


if __name__ == '__main__':

    with open('/home/elkasitu/Images/Steganography_original.png', 'rb') as f:
        buf = f.read()

    d = PNGDecoder(buf)
    d.decode()
    d.inflate()
    d.defilter()
    img = d.image
    pygame.init()
    screen = pygame.display.set_mode((img.width, img.height))
    pygame.surfarray.blit_array(screen, img.interlaced)
    pygame.display.flip()
    while True:
        pass
