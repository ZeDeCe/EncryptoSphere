import os
from zfec.easyfec import Encoder
from zfec.easyfec import Decoder

#from .Split import Split
from modules.Split.Split import Split

class ShamirSplit(Split):
    
    @staticmethod
    def get_name():
        return "Shamir"

    def split(self, data, clouds_num):
        num_parts= clouds_num * 2
        min_parts=3
        encoder = Encoder(k=min_parts, m=num_parts)
        try:
            data_parts =  encoder.encode(data)
            return [data_parts[i:i + clouds_num] for i in range(0, len(data_parts), clouds_num)]

        except Exception:
            raise Exception("Shamir: Error during split")


    def merge_parts(self, data, clouds_num):
        num_parts= clouds_num * 2
        min_parts=3
        sharenums = []
        if (len(data) != num_parts):
            print(len(data))
            raise Exception("Shamir: Number of parts does not match data given!")
        if len(data) < min_parts:
            raise Exception(f"Shamir: At least {min_parts} parts are required to reconstruct the file.")
        
        for i in range(0, num_parts):
            sharenums.append(i)

        decoder = Decoder(k=min_parts, m=num_parts)
        data = data[:min_parts]
        sharenums = sharenums[:min_parts]

        try:
            padlen = 0
            return decoder.decode(data, sharenums, padlen)
            #decoded_data = decoder.decode(data, sharenums, padlen)
            #output_file = r"C:\\Users\\hadas\\Desktop\\final_project\\output.txt" #path to the output file
            #with open(output_file, 'wb') as output:
            #    output.write(decoded_data)
        except Exception:
            raise Exception("Shamir: error during reconstruction")

"""
def test():
    print("1. Split a file into parts")
    print("2. Merge parts into the original file")
    print("3. Exit")

    choice = input("Enter your choice: ")
    split = ShamirSplit()

    if choice == '1':
        file_path = r"C:\\Users\\hadas\\Desktop\\final_project\\test.txt" #path to the file you want to split
        if os.path.exists(file_path):
            with open(file_path, 'rb') as file:
                data = file.read()
            splited = split.split(data, 2)
            print(splited)
            print("now merging")
            split.merge_parts(splited)
        else:
            print("Error: File not found.")
    elif choice == '2':
            split.merge_parts(data)

    elif choice == '3':
        print("Exiting...")"
"""