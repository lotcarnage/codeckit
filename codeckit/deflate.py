import numpy

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
        return value

def __fix_huffman_decode_to_literal_value(bitreader):
    v = bitreader.read(7)
    if v <= 0b0010111: # type C
        return 256 + v
    elif 0b0011000 <= v <= 0b1011111: # type A
        remain_bits = bitreader.read(1)
        v = (v << 1) | remain_bits
        return 0 + v - 0b00110000
    elif 0b1100100 <= v <= 0b1111111: # type B
        remain_bits = bitreader.read(2)
        v = (v << 2) | remain_bits
        return 144 + v - 0b110010000
    elif 0b1100000 <= v <= 0b1100011: # type D
        remain_bits = bitreader.read(1)
        v = (v << 1) | remain_bits
        return 280 + v - 0b11000000

def __hclen_decode(bitreader, HCLEN):
    # テーブルにはアルファベット順では無い並びでハフマン符号長が保存されている
    shuffled = numpy.array([bitreader.read(3) for _ in range(HCLEN)])
    index_table = [
        16, 17, 18,  0,  8,  7,  9,  6,
        10,  5, 11,  4, 12,  3, 13,  2,
        14,  1, 15]
    code_length_array = numpy.zeros(19, dtype=int)
    # アルファベット順にハフマン符号長を並び替える
    # 存在しないアルファベットは0
    # ここでのアルファベットは
    # リテラル／長さや距離を保存するハフマン符号の符号長
    # よって0〜18の値がアルファベットである
    code_length_array[index_table[:len(shuffled)]] = shuffled
    return list(code_length_array)


def __construct_hclen_huffman_code_table(hclen_array):
    # RFC 1951 3.2.2 のルールに基づく
    # Step1 ビット長毎の数え上げ
    N = len(hclen_array)
    bl_count = [hclen_array.count(i) for i in range(N)]
    # Step2 各ビット長へ割り当て可能なビットパターン範囲の計算
    code = 0
    bl_count[0] = 0
    lower_value = numpy.zeros(N, dtype=int)
    for bits in range(1, N):
        code = (code + bl_count[bits - 1]) << 1
        if bl_count[bits] != 0:
            lower_value[bits] = code
    # Step3 同一符号長内において、
    # アルファベット辞書順に連番でビットパターンを割り当てる
    code_table = []
    for bits in range(1, N):
        alphabet_list = [i for i, bl in enumerate(hclen_array) if bits == bl]
        if len(alphabet_list) != 0:
            alphabet_list = sorted(alphabet_list)
            for i, alphabet in enumerate(alphabet_list):
                code_value = lower_value[bits] + i
                code_bits = "{{:0{}b}}".format(bits).format(code_value)
                code_table.append((alphabet, code_bits))
    # 有効なアルファベットと符合ビットパターンをタプルの配列で返す
    return code_table

def __decode_dynamic_huffman_block(bitreader):
    HLIT = bitreader.read(5) + 257
    HDIST = bitreader.read(5) + 1
    HCLEN = bitreader.read(4) + 4
    print(HLIT, HDIST, HCLEN)

    # 各ハフマンテーブルの符号長をハフマン符号化した際の符号長を読み込む
    hclen_array = __hclen_decode(bitreader, HCLEN)
    print(hclen_array)

    # ハフマンテーブルを再構築
    length_count = [(cl, hclen_array.count(cl)) for cl in set(hclen_array) if cl != 0]
    print(length_count)
    code_table = __construct_hclen_huffman_code_table(hclen_array)
    print(code_table)

    # HCLENハフマンテーブルを使って、各ハフマンテーブルを複合する


    return None

def __decode(deflated_bytearray):
    bitreader = BitReader(deflated_bytearray)
    v = bitreader.read(1)
    print("End block" if v == 1 else "block")
    compress_type_string = [
        "00:uncompressed",
        "01:fixed huffman",
        "10:dynamic huffman",
        "11:error block",
    ]
    compress_type = bitreader.read(2)
    print(compress_type_string[compress_type])

    if compress_type == 0b01:
        v = __fix_huffman_decode_to_literal_value(bitreader)
        print(v)
    elif compress_type == 0b10:
        __decode_dynamic_huffman_block(bitreader)

    return None

if __name__ == "__main__":
    with open("deflate.py", "rb") as data_file:
        data = data_file.read()
    import zlib
    zlib_deflated = zlib.compress(data)[2:-4]
    __decode(zlib_deflated)
    exit(0)
