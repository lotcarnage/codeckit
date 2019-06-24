if __name__ == "__main__":
    import codeckit.blocksort
    data = [7,1,3,5,2,1,2,54,7,32]
    index, encoded = codeckit.blocksort.encode(data)
    decoded = codeckit.blocksort.decode(index, encoded)
    print(data)
    print(encoded)
    print(decoded)

    import codeckit.huffman as huffman
    encoded = huffman.encode(bytes(data))
    decoded = huffman.decode(encoded)
    print(data)
    print(decoded)

    exit()
