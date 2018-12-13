

class PNGChunk:

    def __init__(self, _len, _type, data, crc):
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


class PNGDecoder:

    def __init__(self, buffer):
        self._internal_counter = 0
        self._buffer = buffer

    def next(self, quantity=1):
        c = self._internal_counter
        if quantity == 1:
            res = self._buffer[c]
            self._internal_counter += 1
        else:
            res = self._buffer[c:c + quantity]
            self._internal_counter += quantity
        return res

    def _get_header(self):
        # PNG format has an 8-byte header
        # should be 0x89 0x50 0x4e 0x47 0x0d 0x0a 0x1a 0x0a
        return self.next(8)

    def _bytes_to_int(self, bytes):
        res = 0
        factor = 1
        for byte in bytes[::-1]:
            res += int(byte) * factor
            factor *= 10
        return res

    def get_next_chunk(self):
        c_len = self._bytes_to_int(self.next(4))
        c_type = self.next(4).decode()
        assert c_len < (len(self._buffer) - self._internal_counter), \
            "Buffer overflow: Length of chunk is %d but only %d bytes remain in buffer" % (
                    c_len, len(self._buffer) - self._internal_counter
                )
        c_data = self.next(c_len)
        c_crc = self.next(4)
        return PNGChunk(c_len, c_type, c_data, c_crc)


if __name__ == '__main__':

    with open('/home/elkasitu/Images/Steganography_original.png', 'rb') as f:
        buf = f.read()

    d = PNGDecoder(buf)
    print(d._get_header())
    c = d.get_next_chunk()
    print(c.type, c.critical, c.len)
