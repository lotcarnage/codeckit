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

    def discard_bits_to_byte_border(self):
        self.remain_bit_count = 0
        return None

    def read_bytes(self, num_bytes):
        if self.remain_bit_count != 0:
            return None
        offset = self.byte_offset
        byte_array = self.byte_array[offset:offset + num_bytes]
        self.byte_offset += num_bytes
        return byte_array

def __decode_noncompressed_block(bitreader):
    # 半端なビットを捨ててバイト境界まで読み飛ばす
    bitreader.discard_bits_to_byte_border()
    header = bitreader.read_bytes(4)
    LEN = header[1] * 256 + header[0] # 格納されているデータ長を復元
    NLEN = header[3] * 256 + header[2] # 格納されているデータ長の補数（LEN + NLEN == 65535となる）
    decoded_data = bitreader.read_bytes(LEN)
    return decoded_data
    
def __decode_hclen_code_length_table(bitreader, HCLEN):
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

def __make_huffman_tree(code_table):
    root = {}
    # 辞書でハフマン木を構築
    # キーは 0 か 1、入っているのは次のノードかアルファベット
    for code_pair in code_table:
        alphabet = code_pair[0]
        code = code_pair[1]
        node = root
        bl = len(code)
        for bit in code:
            bit = int(bit)
            if bit in node:
                node = node[bit]
            else:
                if bl == 1:
                    node[bit] = alphabet
                else:
                    new_node = {}
                    node[bit] = new_node
                    node = new_node
            bl = bl - 1
    return root

def __decode_huffman_encoded_value(huffman_tree, bitreader):
    node = huffman_tree
    while(True):
        bit = bitreader.read(1)
        v = node[bit]
        if type(v) is int:
            return v
        else:
            node = v
    return None

def __decode_codelength_table(
        hclen_huffman_tree, bitreader, table_size):
    cl_table = numpy.zeros(table_size, dtype=int)
    cl_table_index = 0
    # RFC 1951 3.2.7 符号長テーブルのデコード
    while(cl_table_index < table_size):
        v = __decode_huffman_encoded_value(hclen_huffman_tree, bitreader);
        if 0 <= v <= 15: # 0～15は符号長がそのまま保存されている
            cl_table[cl_table_index] = v
            cl_table_index += 1
        else: # 16～18はランレングスであり、直前の符号長を繰り返す
            # 繰り返し回数を読み込む
            if v == 16:
                # 00～11が3～6に対応
                repeat_times = bitreader.read(2) + 3
                # 直前のコード長を繰り返す
                code = cl_table[cl_table_index-1]
            elif v == 17:
                # 000～111が3～10に対応
                repeat_times = bitreader.read(3) + 3
                # 0を繰り返す
                code = 0
            else: # v == 18 は自明
                # 000000～1111111が11～138に対応
                repeat_times = bitreader.read(7) + 11
                # 0を繰り返す
                code = 0
            cl_table[cl_table_index:cl_table_index+repeat_times] = code
            cl_table_index += repeat_times
    return list(cl_table)

def __decode_length(bitreader, literal):
    if 257 <= literal <= 264:
        length = literal - 257 + 3
    elif 265 <= literal <= 268:
        ext_bits = bitreader.read(1)
        length = (((literal - 265) << 1) | ext_bits) + 11
    elif 269 <= literal <= 272:
        ext_bits = bitreader.read(2)
        length = (((literal - 269) << 2) | ext_bits) + 19
    elif 273 <= literal <= 276:
        ext_bits = bitreader.read(3)
        length = (((literal - 273) << 3) | ext_bits) + 35
    elif 277 <= literal <= 280:
        ext_bits = bitreader.read(4)
        length = (((literal - 277) << 4) | ext_bits) + 67
    elif 281 <= literal <= 284:
        ext_bits = bitreader.read(5)
        length = (((literal - 281) << 5) | ext_bits) + 131
    else: # literal == 285
        length = 258
    return length

def __decode_distance(bitreader, distance_type):
    if 0 <= distance_type <= 3:
        distance = distance_type - 0 + 1
    elif 4 <= distance_type <= 5:
        ext_bits = bitreader.read(1)
        distance = (((distance_type - 4) << 1) | ext_bits) + 5
    elif 6 <= distance_type <= 7:
        ext_bits = bitreader.read(2)
        distance = (((distance_type - 6) << 2) | ext_bits) + 9
    elif 8 <= distance_type <= 9:
        ext_bits = bitreader.read(3)
        distance = (((distance_type - 8) << 3) | ext_bits) + 17
    elif 10 <= distance_type <= 11:
        ext_bits = bitreader.read(4)
        distance = (((distance_type - 10) << 4) | ext_bits) + 33
    elif 12 <= distance_type <= 13:
        ext_bits = bitreader.read(5)
        distance = (((distance_type - 12) << 5) | ext_bits) + 65
    elif 14 <= distance_type <= 15:
        ext_bits = bitreader.read(6)
        distance = (((distance_type - 14) << 6) | ext_bits) + 129
    elif 16 <= distance_type <= 17:
        ext_bits = bitreader.read(7)
        distance = (((distance_type - 16) << 7) | ext_bits) + 257
    elif 18 <= distance_type <= 19:
        ext_bits = bitreader.read(8)
        distance = (((distance_type - 18) << 8) | ext_bits) + 513
    elif 20 <= distance_type <= 21:
        ext_bits = bitreader.read(9)
        distance = (((distance_type - 20) << 9) | ext_bits) + 1025
    elif 22 <= distance_type <= 23:
        ext_bits = bitreader.read(10)
        distance = (((distance_type - 22) << 10) | ext_bits) + 2049
    elif 24 <= distance_type <= 25:
        ext_bits = bitreader.read(11)
        distance = (((distance_type - 24) << 11) | ext_bits) + 4097
    elif 26 <= distance_type <= 27:
        ext_bits = bitreader.read(12)
        distance = (((distance_type - 26) << 12) | ext_bits) + 8193
    elif 28 <= distance_type <= 29:
        ext_bits = bitreader.read(13)
        distance = (((distance_type - 28) << 13) | ext_bits) + 16385
    else: # error
        raise "data error"
    return distance

def __lz77_decompress_inplace(decompressed_data, backward_distance, length):
    start_offset = len(decompressed_data) - backward_distance
    for offset in range(start_offset, start_offset + length, 1):
        alphabet = decompressed_data[offset]
        decompressed_data.append(alphabet)
    return None

def __decode_dynamic_huffman_tree(bitreader):
    HLIT = bitreader.read(5) + 257
    HDIST = bitreader.read(5) + 1
    HCLEN = bitreader.read(4) + 4
    # 各ハフマンテーブルの符号長をハフマン符号化した際の符号長を読み込む
    hclen_array = __decode_hclen_code_length_table(bitreader, HCLEN)
    # ハフマンテーブルを再構築
    hclen_cl_table = __construct_hclen_huffman_code_table(hclen_array)
    hclen_huffman_tree = __make_huffman_tree(hclen_cl_table)
    # HCLENハフマンテーブルを使って、各ハフマンテーブルを複合する
    literal_cl_table = __decode_codelength_table(hclen_huffman_tree, bitreader, HLIT)
    distance_cl_table = __decode_codelength_table(hclen_huffman_tree, bitreader, HDIST)
    # 各種ハフマン木を構築
    literal_huffman_code_table = __construct_hclen_huffman_code_table(literal_cl_table)
    literal_huffman_tree = __make_huffman_tree(literal_huffman_code_table)
    distance_huffman_code_table = __construct_hclen_huffman_code_table(distance_cl_table)
    distance_huffman_tree = __make_huffman_tree(distance_huffman_code_table)
    return literal_huffman_tree, distance_huffman_tree

def __decode_dynamic_huffman_block(bitreader):
    # 各種ハフマン木を構築
    literal_huffman_tree, distance_huffman_tree = __decode_dynamic_huffman_tree(bitreader)

    # データの復号
    decoded_data = bytearray()
    while(True):
        literal_or_length = __decode_huffman_encoded_value(literal_huffman_tree, bitreader);
        if 0 <= literal_or_length <= 255:
            # literal
            decoded_data.append(literal_or_length)
        elif literal_or_length == 256:
            # end
            break
        else: # 257 <= literal_or_length <= 285
            # length and distance
            length = __decode_length(bitreader, literal_or_length)
            distance_type = __decode_huffman_encoded_value(distance_huffman_tree, bitreader);
            distance = __decode_distance(bitreader, distance_type)
            __lz77_decompress_inplace(decoded_data, distance, length)

    return decoded_data

def __make_fixed_huffman_code_length_table():
    code_length_table = numpy.zeros(286, dtype=int)
    code_length_table[0:144] = 8
    code_length_table[144:256] = 9
    code_length_table[256:280] = 7
    code_length_table[280:288] = 8
    return list(code_length_table)

def __decode_fixed_huffman_tree(bitreader):
    literal_cl_table = __make_fixed_huffman_code_length_table()
    literal_huffman_code_table = __construct_hclen_huffman_code_table(literal_cl_table)
    literal_huffman_tree = __make_huffman_tree(literal_huffman_code_table)
    return literal_huffman_tree

def __decode_fixed_huffman_compressed_block(bitreader):
    literal_huffman_tree = __decode_fixed_huffman_tree(bitreader)

    # データの復号
    decoded_data = bytearray()
    while(True):
        literal_or_length = __decode_huffman_encoded_value(literal_huffman_tree, bitreader);
        if 0 <= literal_or_length <= 255:
            # literal
            decoded_data.append(literal_or_length)
        elif literal_or_length == 256:
            # end
            break
        else: # 257 <= literal_or_length <= 285
            # length and distance
            length = __decode_length(bitreader, literal_or_length)
            distance_type = bitreader.read(5);
            distance = __decode_distance(bitreader, distance_type)
            __lz77_decompress_inplace(decoded_data, distance, length)

    return decoded_data

def __decode(deflated_bytearray):
    bitreader = BitReader(deflated_bytearray)
    decoded_data = bytearray()
    is_end_block = False
    while(not is_end_block):
        is_end_block = bool(bitreader.read(1))
        compress_type = bitreader.read(2)
        if compress_type == 0b01:
            decoded_block_data = __decode_fixed_huffman_compressed_block(bitreader)
        elif compress_type == 0b10:
            decoded_block_data = __decode_dynamic_huffman_block(bitreader)
        elif compress_type == 0b00:
            decoded_block_data = __decode_noncompressed_block(bitreader)
        else:
            raise "Invalid datastream error!"
        decoded_data.extend(decoded_block_data)

    return decoded_data

if __name__ == "__main__":
    def __test_decommpress_deflate(raw_data, compress_level, output_filepath):
        import zlib
        zlib_deflated = zlib.compress(raw_data, compress_level)[2:-4]
        decoded_data = __decode(zlib_deflated)
        with open(output_filepath, "wb") as decoded_file:
            decoded_file.write(decoded_data)

    with open("deflate.py", "rb") as data_file:
        data = data_file.read()
    __test_decommpress_deflate(data, -1, "deflate_10.py")
    __test_decommpress_deflate(data, 0, "deflate_00.py")
    __test_decommpress_deflate(bytearray("abcdefg".encode()), 1, "deflate_01.py")

    exit(0)
