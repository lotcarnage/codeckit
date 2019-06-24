from operator import itemgetter

def __make_rotated_table(array):
    copied = array.copy()
    table = [copied.copy()]
    for i in range(1, len(copied)):
        copied.append(copied.pop(0))
        table.append(copied.copy())
    return table

def __argsort(array):
    return sorted(range(len(array)), key=array.__getitem__)

def encode(array):
    length = len(array)
    table = __make_rotated_table(array)
    for i in range(length-1, -1, -1):
        table.sort(key=itemgetter(i))
    index = table.index(list(array))
    encoded = [row[-1] for row in table]
    return index, encoded

def decode(index, array):
    next_index_table = __argsort(array)
    decoded = []
    i = index
    for _ in range(len(array)):
        i = next_index_table[i]
        decoded.append(array[i])
    return decoded

if __name__ == "__main__":
    import unittest
    class TestBlocksort(unittest.TestCase):
        def test_value_array_encodeing(self):
            data = [4,2,3,3,4,2,1,5]
            index, encoded = encode(data)
            decoded = decode(index, encoded)
            self.assertEqual(data, decoded)
            print(data)
            print(encoded)
            print(decoded)

    unittest.main()
    exit()
