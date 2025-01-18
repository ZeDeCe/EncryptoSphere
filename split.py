import os
from zfec.easyfec import Encoder
from zfec.easyfec import Decoder

def split_file(file_path, num_parts=4, min_parts=3):
    encoder = Encoder(k=3, m=4)
    with open(file_path, 'rb') as file:
        data = file.read()

    parts = encoder.encode(data)
    original_filename = os.path.splitext(os.path.basename(file_path))[0]

    part_paths = []
    parts_folder = r'c:\check\split_parts'
    os.makedirs(parts_folder, exist_ok=True)

    for i, part in enumerate(parts):
        part_filename = f'{original_filename}_{i + 1}.bin'
        part_path = os.path.join(parts_folder, part_filename)
        with open(os.path.join(parts_folder, part_filename), 'wb') as part_file:
            part_file.write(part)
        part_paths.append(part_path)

    print(f"File '{file_path}' split into {num_parts} parts in folder '{parts_folder}'.")
    return part_paths


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
    
    if len(parts) > min_parts:
        parts = parts[:min_parts]
        sharenums = sharenums[:min_parts]
    
    decoder = Decoder(k=3, m=4)
    print(parts)

    try:
        padlen = 0

        decoded_data = decoder.decode(parts, sharenums, padlen)

        with open(output_file, 'wb') as output:
            output.write(decoded_data)

        print(f"File successfully reconstructed into '{output_file}'.")
    except Exception as e:
        print(f"Error during reconstruction: {e}")

def generate_file_names(file_name, num_parts=4, new_extension=".bin"):
    base_name, _ = os.path.splitext(file_name)
    extension = new_extension if new_extension else os.path.splitext(file_name)[1]
    return [f"{base_name}_{i + 1}{extension}" for i in range(num_parts)]

def merge_parts_by_paths(file_paths, file_name, min_parts=3):
    parts = []
    sharenums = []
    dest_path = os.path.join(os.path.expanduser("~"), "Downloads", file_name)
    
    for i, part_path in enumerate(file_paths):
        if os.path.exists(part_path):
            with open(part_path, 'rb') as part_file:
                parts.append(part_file.read())
                sharenums.append(i)

    if len(parts) < min_parts:
        print(f"Error: At least {min_parts} parts are required to reconstruct the file.")
        return
    
    if len(parts) > min_parts:
        parts = parts[:min_parts]
        sharenums = sharenums[:min_parts]
    
    decoder = Decoder(k=3, m=4)

    try:
        padlen = 0

        decoded_data = decoder.decode(parts, sharenums, padlen)

        with open(dest_path, 'wb') as output:
            output.write(decoded_data)

        print(f"File successfully reconstructed into '{dest_path}'.")
    except Exception as e:
        print(f"Error during reconstruction: {e}")


def main():
    print("1. Split a file into parts")
    print("2. Merge parts into the original file")
    print("3. Exit")

    choice = input("Enter your choice: ")

    if choice == '1':
        file_path = input("Enter file path: ")
        if os.path.exists(file_path):
            split_file(file_path)
        else:
            print("Error: File not found.")
    elif choice == '10': #ignore
        parts_folder = "split_parts"
        output_file = "merged.txt" 
        if os.path.exists(parts_folder):
            merge_parts(parts_folder, output_file)
        else:
            print("Error: Folder not found.")
    elif choice == '2':
        file_name = input("enter file name to merge: ")
        parts_pathes = generate_file_names(file_name)
        parts_folder = r'c:\check\split_parts'
        file_paths = [os.path.join(parts_folder, file_name) for file_name in parts_pathes]

        print(file_paths)
        merge_parts_by_paths(file_paths, file_name)
    elif choice == '3':
        print("Exiting...")


if __name__ == '__main__':
    main()
