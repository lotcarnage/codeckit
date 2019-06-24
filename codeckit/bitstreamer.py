import numpy

def _reverse_bit_order(value, bit_count):
    f = "{:0" + str(bit_count) + "b}"
    return int("0b" + f.format(value)[::-1], 0)

class BitWriter:
    def __init__(self, size):
        self.byte_array = numpy.zeros(size, dtype=numpy.uint8)
        self.bit_offset = 0
        self.byte_offset = 0
        self.tmp_byte = 0

    def __write_bits(self, value, bits):
        if 8 <= self.bit_offset + bits:
            remain_bits = 8 - self.bit_offset
            bit_mask = 2 ** remain_bits - 1
            byte = self.tmp_byte
            byte = byte | ((value & bit_mask) << self.bit_offset)
            value = value >> remain_bits
            bits -= remain_bits
            self.bit_offset = 0
            self.byte_array[self.byte_offset] = byte
            self.byte_offset += 1
            self.tmp_byte = 0
        else:
            remain_bits = bits
            bit_mask = 2 ** remain_bits - 1
            byte = self.tmp_byte
            byte = byte | ((value & bit_mask) << self.bit_offset)
            self.bit_offset += bits
            self.tmp_byte = byte
            bits = 0
        return value, bits

    def write(self, value, bits):
        value = _reverse_bit_order(value, bits)
        while 0 < bits:
            if 0 < self.bit_offset:
                value, bits = self.__write_bits(value, bits)
            else:
                if 8 <= bits:
                    self.byte_array[self.byte_offset] = value & 0x000000ff
                    self.byte_offset += 1
                    bits -= 8
                    value = value >> 8
                else:
                    self.bit_offset = bits
                    bit_mask = 2 ** bits - 1
                    self.tmp_byte = value & bit_mask
                    bits = 0

    def get(self):
        byte_array = numpy.copy(self.byte_array)
        if 0 < self.bit_offset:
            byte_array[self.byte_offset] = self.tmp_byte
        return byte_array, self.bit_offset


class BitReader:
    def __init__(self, byte_array):
        self.byte_array = byte_array
        self.byte_offset = 0
        self.tmp_byte = 0
        self.remain_bit_count = 0

    def __read_bit(self, value, write_offset, bit_count):
        if self.remain_bit_count == 0:
            self.tmp_byte = self.byte_array[self.byte_offset]
            self.remain_bit_count = 8
            self.byte_offset += 1

        write_bit_count = min([self.remain_bit_count, bit_count])
        bit_mask = 2 ** write_bit_count - 1
        byte = self.tmp_byte
        value |= (byte & bit_mask) << write_offset
        self.tmp_byte = byte >> write_bit_count
        self.remain_bit_count -= write_bit_count
        bit_count -= write_bit_count
        write_offset += write_bit_count
        return value, write_offset, bit_count

    def read(self, bit_count):
        value = 0
        write_offset = 0
        need_bit_count = bit_count
        while 0 < bit_count:
            value, write_offset, bit_count = self.__read_bit(value, write_offset, bit_count)
        return _reverse_bit_order(value, need_bit_count)
