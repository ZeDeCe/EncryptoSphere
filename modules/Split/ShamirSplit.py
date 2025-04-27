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

        except Exception as e:
            raise Exception(f"Shamir-Split Error: {e}")


    def merge_parts(self, data, clouds_num):
        num_parts= clouds_num * 2
        min_parts=3
        sharenums = []

        # Filter out None values and construct sharenums
        sharenums = [i for i, part in enumerate(data) if part is not None]
        data = [part for part in data if part is not None]

        if len(data) < min_parts:
            raise Exception(f"Shamir-Merge: At least {min_parts} parts are required to reconstruct the file, got {len(data)} parts")

        decoder = Decoder(k=min_parts, m=num_parts)
        if len(data) > min_parts:
            data = data[:min_parts]
            sharenums = sharenums[:min_parts]

        try:
            padlen = 0
            return decoder.decode(data, sharenums, padlen)

        except Exception as e:
            raise Exception(f"Shamir-Merge: error during reconstruction, {e}")

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
            print("File data:", data)
            splited = split.split(data, 2)
            print("Splitted data:", splited)
            flattened_parts = [item for sublist in splited for item in sublist]
           # Create indices for the parts
            indices = list(range(len(flattened_parts)))

            # Shuffle the parts and indices
            combined = list(zip(flattened_parts, indices))
            random.shuffle(combined)
            shuffled_parts, shuffled_indices = zip(*combined)

            print("Shuffled parts:", shuffled_parts)
            print("Shuffled indices:", shuffled_indices)

            # Merge the shuffled parts
            print("Now merging...")
            reconstructed_data = split.merge_parts(flattened_parts, 2)
            print("Reconstructed data:", reconstructed_data)
        else:
            print("Error: File not found.")
    elif choice == '2':
            data = [b"1\r\n2\r\n3\r\n", b"\r\r\n6\r\n'#6", b"4\r\n5\r\n6\x00\x00"]
            print(split.merge_parts(data, 2, [0, 2, 1]))
            print(split.merge_parts(data, 2, [0, 3, 1]))


    elif choice == '3':
        print("Exiting...")

if __name__ == "__main__":
    test()
"""