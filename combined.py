from DropBox import DropboxImp
from GoogleDrive import GoogleDriveImp
from split import split_file
from split import merge_parts_by_paths
from split import generate_file_names

import os


def authenticate(drive_service, dropbox_Service):
    print("authenticate to clouds")
    #Google Drive
    drive_service.authenticate_google_drive()
    if not drive_service:
        print("Authentication failed.")
        return

    email = input("Enter your Dropbox email address: ")
    print(f"Authenticating {email}'s Dropbox account...")
    success = dropbox_Service.authenticate_dropbox(email)
    if not success:
        print("Authentication failed.")
        return

def upload_file(drive_service, dropbox_Service, all_files):

    print("Found files:", all_files)
    if len(all_files) < 4:
        print("Error: Not enough files in the folder.")
    else:
        cloud1 = all_files[:2]  
        cloud2 = all_files[2:4]  

        for file in cloud1:
            drive_service.upload_file(file)

        dest_file_names = [f'/{os.path.basename(file)}' for file in cloud2]
        for file, dest_name in zip(cloud2, dest_file_names):
            dropbox_Service.upload_file(file, dest_name)

def merge_file():
    return

def download_file(drive_service, dropbox_service, files):
    cloud1 = files[:2]  
    cloud2 = files[2:4]  

    parts_paths = []
    for file in cloud1:
        parts_paths.append(drive_service.download_file(file))

    dest_file_names = [f'/{os.path.basename(file)}' for file in cloud2]
    for file in dest_file_names:
        parts_paths.append(dropbox_service.download_file(file))

    return parts_paths
    
def main():
    drive_service = GoogleDriveImp()
    dropbox_Service = DropboxImp()
    # auth
    authenticate(drive_service, dropbox_Service)

    while True:
        print("\nSelect an action:")
        print("1. Upload a file")
        print("2. download a file")
        print("3. Exit")

        choice = input("Enter your choice: ")

        if choice == '1':
            # split
            file_path = input("please enter path to file you want to upload: ")
            if os.path.exists(file_path):
                split_parts_paths = split_file(file_path)
                print(split_parts_paths)
                # upload
                upload_file(drive_service, dropbox_Service, split_parts_paths)
            else:
                print("Error: File not found.")

        elif choice == '2':
            # download
            file_name = input("please enter the name of the file you want to download: ")
            files = generate_file_names(file_name)
            parts_pathes = download_file(drive_service, dropbox_Service, files)
            merge_parts_by_paths(parts_pathes, file_name)

        elif choice == '3':
            print("Exiting...")
            break

        else:
            print("Invalid choice, please try again.")



if __name__ == '__main__':
    main()

