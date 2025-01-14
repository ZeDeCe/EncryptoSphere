import os
from zfec.easyfec import Encoder
from zfec.easyfec import Decoder

def split_file(file_path, num_parts=4, min_parts=3):
    encoder = Encoder(k=3, m=4)
    with open(file_path, 'rb') as file:
        data = file.read()

    parts = encoder.encode(data)

    parts_folder = 'split_parts'
    os.makedirs(parts_folder, exist_ok=True)

    for i, part in enumerate(parts):
        with open(os.path.join(parts_folder, f'part_{i + 1}.bin'), 'wb') as part_file:
            part_file.write(part)

    print(f"File '{file_path}' split into {num_parts} parts in folder '{parts_folder}'.")


def merge_parts(parts_folder, output_file, num_parts=4, min_parts=3):
    parts = []
    sharenums = []
    for i in range(1, num_parts + 1):
        part_path = os.path.join(parts_folder, f'part_{i}.bin')
        if os.path.exists(part_path):
            with open(part_path, 'rb') as part_file:
                parts.append(part_file.read())
                sharenums.append(i - 1)

    if len(parts) < min_parts:
        print(f"Error: At least {min_parts} parts are required to reconstruct the file.")
        return

    decoder = Decoder(k=3, m=4)

    try:
        padlen = 0

        decoded_data = decoder.decode(parts, sharenums, padlen)

        with open(output_file, 'wb') as output:
            output.write(decoded_data)

        print(f"File successfully reconstructed into '{output_file}'.")
    except Exception as e:
        print(f"Error during reconstruction: {e}")


def main():
    print("1. Split a file into parts")
    print("2. Merge parts into the original file")
    print("3. Exit")

    choice = input("Enter your choice: ")

    if choice == '1':
        file_path = "test.txt" #path to the file you want to split
        if os.path.exists(file_path):
            split_file(file_path)
        else:
            print("Error: File not found.")
    elif choice == '2':
        parts_folder = "split_parts"
        output_file = "merged.txt" 
        if os.path.exists(parts_folder):
            merge_parts(parts_folder, output_file)
        else:
            print("Error: Folder not found.")
    elif choice == '3':
        print("Exiting...")


if __name__ == '__main__':
    main()
