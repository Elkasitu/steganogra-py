

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


class PNGImage:

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


if __name__ == '__main__':

    with open('/home/elkasitu/Images/Steganography_original.png', 'rb') as f:
        buf = f.read()

    d = PNGDecoder(buf)
    d.decode()
    print(d.image.width, d.image.height, d.image.depth, d.image.color_type, d.image.cmp_method,
          d.image.filter_method, d.image.int_method, d.image.palette)
