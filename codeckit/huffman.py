import numpy
from .bitstreamer import *

def __make_histgram(values):
    histgram = {}
    for v in values:
        v_key = str(v)
        if v_key in histgram:
            histgram[v_key] += 1
        else:
            histgram[v_key] = 1
    return histgram

def __make_huffman_tree(histgram):
    class Node:
        def __init__(self, key, count, is_leaf):
            self.count = count
            self.is_leaf = is_leaf
            self.parent_index = -1
            self.key = key
            self.code_length = 0
        def __lt__(self, other):
            return self.count < other.count
        def __str__(self):
            return "{:s}:{:d}:{:d}".format(
                        self.key, self.count, self.code_length)

    nodes = []
    for key, v in histgram.items():
        nodes.append(Node(key, v, True))
    num_leaf = len(nodes)

    nodes = sorted(nodes, reverse=True)
    index_stack = [i for i in range(len(nodes))]
    while 1 < len(index_stack):
        min1_index = index_stack.pop()
        min2_index = index_stack.pop()
        node_count = nodes[min1_index].count + nodes[min2_index].count
        node_index = len(nodes)
        nodes[min1_index].parent_index = node_index
        nodes[min2_index].parent_index = node_index
        nodes.append(Node(None, node_count, False))
        is_inserted = False
        for i, index in enumerate(index_stack[::-1]):
            if node_count < nodes[index].count:
                index_stack.insert(len(index_stack) - i, node_index)
                is_inserted = True
                break
        else:
            if is_inserted == False:
                index_stack.insert(0, node_index)

    total_bit_count = numpy.uint64(0)
    for i, leaf in enumerate(nodes[:num_leaf]):
        parent_index = leaf.parent_index
        while parent_index != -1:
            leaf.code_length += 1
            parent_index = nodes[parent_index].parent_index
        #leaf.code_length += 1
        nodes[i] = leaf
        total_bit_count = total_bit_count + leaf.code_length * leaf.count

    return nodes[:num_leaf], numpy.uint64(total_bit_count)

def __normalize_huffman_tree(huffman_tree_leafs):
    class Symbol:
        def __init__(self, leaf):
            self.key = int(leaf.key)
            self.code_length = leaf.code_length
        def __lt__(self, other):
            if self.code_length == other.code_length:
                return self.key < other.key
            else:
                return self.code_length < other.code_length
        def __str__(self):
            return "{:4d}:{:3d}".format(
                        self.key, self.code_length)

    symbols = []
    for leaf in huffman_tree_leafs:
        symbols.append(Symbol(leaf))
    return sorted(symbols)

def __make_huffman_code_table(symbols):
    code_array = numpy.zeros(len(symbols), dtype=numpy.uint32)
    code = 0
    last_l = symbols[0].code_length
    code_array[0] = code
    for i, symbol in enumerate(symbols[1:]):
        code += 1
        if last_l < symbol.code_length:
            code *= 2 ** (symbol.code_length - last_l)
        code_array[i + 1] = code
        last_l = symbol.code_length
    return code_array

def __bit_width(value):
    return len("{:b}".format(value))

def __serialize_normalized_huffman_tree(symbols):
    first_length = symbols[0].code_length
    num_symbols = len(symbols) - 1
    num_symbols_bytes = (__bit_width(num_symbols) + 7) // 8
    max_symbol = max(symbols, key=(lambda x:x.key))
    symbol_bits = __bit_width(max_symbol.key)

    last_length = first_length
    max_length = 0
    for i in range(len(symbols)):
        diff_length = symbols[i].code_length - last_length
        last_length = symbols[i].code_length
        symbols[i].code_length = diff_length
        if max_length < diff_length:
            max_length = diff_length
    diff_length_bit_count = __bit_width(max_length)

    header = numpy.zeros(4 + num_symbols_bytes, dtype=numpy.uint8)
    header[0] = first_length
    header[1] = diff_length_bit_count
    header[2] = num_symbols_bytes
    for i, offset in enumerate(range(3,3+num_symbols_bytes)):
        header[offset] = num_symbols & 0x000000ff
        num_symbols = num_symbols >> 8
    header[3 + num_symbols_bytes] = symbol_bits

    total_bits = (symbol_bits + diff_length_bit_count) * len(symbols)
    total_bytes = (total_bits + 7) // 8
    bit_stream = BitWriter(total_bytes)
    for symbol in symbols:
        bit_stream.write(symbol.key, symbol_bits)
        bit_stream.write(symbol.code_length, diff_length_bit_count)
    byte_array, last_bits = bit_stream.get()
    data = numpy.r_[header, byte_array]
    return data

def __deserialize_normalized_huffman_tree(byte_array):
    first_length = byte_array[0]
    diff_length_bit_count = byte_array[1]
    num_symbols_byte_size = byte_array[2]
    num_symbols = 0
    for i, offset in enumerate(range(3,3+num_symbols_byte_size)):
        num_symbols |= (int(byte_array[offset]) & 0x000000ff) << (8 * i)
    num_symbols += 1
    symbol_bits = byte_array[3 + num_symbols_byte_size]

    class Symbol:
        def __init__(self, key, code_length):
            self.key = key
            self.code_length = code_length
        def __str__(self):
            return "{:4d}:{:3d}".format(
                        self.key, self.code_length)

    symbols = []
    bit_reader = BitReader(byte_array[4 + num_symbols_byte_size:])
    last_code_length = first_length
    for i in range(num_symbols):
        key = bit_reader.read(symbol_bits)
        length = bit_reader.read(diff_length_bit_count) + last_code_length
        symbols.append(Symbol(key, length))
        last_code_length = length

    total_bits = (symbol_bits + diff_length_bit_count) * num_symbols
    total_bytes = (total_bits + 7) // 8
    return symbols, 4 + num_symbols_byte_size + total_bytes

def __serialize_data_header(bit_count):
    byte_count = int(bit_count // 8)
    bit_count = int(bit_count % 8)
    byte_count_size = (__bit_width(byte_count) + 7) // 8
    data_header = numpy.zeros(2 + byte_count_size, dtype=numpy.uint8)
    data_header[0] = byte_count_size
    for i, offset in enumerate(range(1,1+byte_count_size)):
        data_header[offset] = int(byte_count) & 0x000000ff
        byte_count = int(byte_count) >> 8
    data_header[1+byte_count_size] = bit_count
    return data_header

def __deserialize_data_header(byte_array):
    byte_count_size = byte_array[0]
    byte_count = 0
    for i, offset in enumerate(range(1,1+byte_count_size)):
        byte_count |= (byte_array[offset] & 0x000000ff) << (8 * i)
    bit_count = byte_array[1+byte_count_size]
    bit_count = bit_count + byte_count * 8
    return bit_count, 2 + byte_count_size

def __encode_data_to_byte_array(symbols, code_table, data, bit_count):
    code_infos = {}
    for symbol, code in zip(symbols, code_table):
        code_infos[symbol.key] = (code, symbol.code_length)

    total_byte_count = (bit_count + 7) // 8
    bitwriter = BitWriter(int(total_byte_count))
    for i, v in enumerate(data):
        code_info = code_infos[v]
        bitwriter.write(code_info[0], code_info[1])

    byte_array, last_bit_count = bitwriter.get()
    return byte_array, last_bit_count

def __make_bit_string(value, bit_count):
    f = "{:0" + str(bit_count) + "b}"
    return f.format(value)

def __make_huffman_code_tree(symbols, code_table):
    class Node:
        def __init__(self):
            self.c0 = None
            self.c1 = None
            self.is_leaf = False
            self.key = None

    root = Node()
    for symbol, code in zip(symbols, code_table):
        bit_string = __make_bit_string(code, symbol.code_length)
        node = root
        for bit in bit_string:
            if bit == "0":
                if node.c0 is None:
                    node.c0 = Node()
                node = node.c0
            else:
                if node.c1 is None:
                    node.c1 = Node()
                node = node.c1
        node.is_leaf = True
        node.key = symbol.key

    return root

def __decode_data_to_byte_array(symbols, code_table, data, bit_count):
    root = __make_huffman_code_tree(symbols, code_table)
    bit_reader = BitReader(data)
    node = root
    decoded_values = []
    for i in range(bit_count):
        v = bit_reader.read(1)
        if v == 0:
            node = node.c0
        else:
            node = node.c1
        if node.is_leaf == True:
            decoded_values.append(node.key)
            node = root

    max_symbol = max(symbols, key=(lambda x: x.key))
    bit_width = __bit_width(max_symbol.key)
    if bit_width <= 8:
        value_type = numpy.uint8
    elif bit_width <= 16:
        value_type = numpy.uint16
    elif bit_width <= 32:
        value_type = numpy.uint32
    else:
        value_type = numpy.uint64

    return numpy.array(decoded_values, value_type)

def encode(values):
    histgram = __make_histgram(values)
    huffman_tree_leafs, bit_count = __make_huffman_tree(histgram)
    normalized_huffman_tree = __normalize_huffman_tree(huffman_tree_leafs)
    code_table = __make_huffman_code_table(normalized_huffman_tree)
    #[print(v, "{:b}".format(code)) for v, code in zip(normalized_huffman_tree, code_table)]
    byte_array, __unuse = __encode_data_to_byte_array(normalized_huffman_tree, code_table, values, bit_count)
    header = __serialize_normalized_huffman_tree(normalized_huffman_tree)
    data_header = __serialize_data_header(bit_count)
    #print("header size:", len(header) + len(data_header))
    #print("data size:", len(byte_array))
    return (numpy.r_[header, data_header, byte_array]).astype(numpy.uint8).tobytes()

def decode(byte_array):
    offset = 0
    symbols, byte_count = __deserialize_normalized_huffman_tree(byte_array)
    offset += byte_count
    bit_count, byte_count = __deserialize_data_header(byte_array[int(offset):])
    offset += byte_count
    code_table = __make_huffman_code_table(symbols)
    #[print(v, "{:b}".format(code)) for v, code in zip(symbols, code_table)]
    decoded_values = __decode_data_to_byte_array(symbols, code_table, byte_array[offset:], bit_count)
    return decoded_values

if __name__ == "__main__":
    with open("huffman.py", "rb") as bin_file:
        binary = bytes(bin_file.read())
    data = numpy.frombuffer(binary, dtype=numpy.uint8)
    encoded = encode(data)
    decoded = decode(encoded)
    print(len(encoded), type(encoded))
    print(len(data), type(data[0]))
    print(len(decoded), type(decoded[0]))
    v = numpy.subtract(data, decoded)
    print(numpy.sum(abs(v)))
