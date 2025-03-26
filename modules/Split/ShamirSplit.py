import os
from zfec.easyfec import Encoder
from zfec.easyfec import Decoder

from .Split import Split

class ShamirSplit(Split):
    def get_name(self):
        return "Shamir"

    def split(self, data, num_parts=4, min_parts=3):
        encoder = Encoder(k=min_parts, m=num_parts)
        try:
            return encoder.encode(data)
        except Exception:
            raise Exception("Shamir: Error during split")


    def merge_parts(self, data, num_parts=4, min_parts=3):
        sharenums = []
        if (len(data) != num_parts):
            raise Exception("Shamir: Number of parts does not match data given!")
        if len(data) < min_parts:
            raise Exception(f"Shamir: At least {min_parts} parts are required to reconstruct the file.")
        
        for i in range(0, num_parts):
            sharenums.append(i)

        decoder = Decoder(k=min_parts, m=num_parts)

        try:
            padlen = 0
            return decoder.decode(data, sharenums, padlen)
        except Exception:
            raise Exception("Shamir: error during reconstruction")


def test():
    print("1. Split a file into parts")
    print("2. Merge parts into the original file")
    print("3. Exit")

    choice = input("Enter your choice: ")
    split = ShamirSplit()

    if choice == '1':
        file_path = "test.txt" #path to the file you want to split
        if os.path.exists(file_path):
            split.split_file(file_path)
        else:
            print("Error: File not found.")
    elif choice == '2':
        parts_folder = "split_parts"
        output_file = "merged.txt" 
        if os.path.exists(parts_folder):
            split.merge_parts(parts_folder, output_file)
        else:
            print("Error: Folder not found.")
    elif choice == '3':
        print("Exiting...")