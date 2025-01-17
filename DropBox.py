#DropBox POC

import dropbox
import webbrowser
import os 

from dotenv import load_dotenv
import dropbox.exceptions 
load_dotenv()

DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")

class DropboxImp:
    def __init__(self):
        self.dbx = None
        self.userid = None

    # Function to authenticate the Dropbox account and get access token
    def authenticate_dropbox(self, email):
        # Start the OAuth flow
        auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(DROPBOX_APP_KEY, DROPBOX_APP_SECRET)

        # Generate the authorization URL
        auth_url = auth_flow.start()

        # Automatically open the URL in the default browser
        print("Opening the authorization page in your browser...")
        webbrowser.open(auth_url)

        print("1. Go to the opened browser tab.")
        print("2. Log in using your Dropbox credentials.")
        print("3. Click 'Allow' to authorize the app.")
        print("4. Copy the authorization code from the URL.")

        # Get the authorization code from the user
        auth_code = input("Enter the authorization code here: ")

        # Verify if the token is valid for the given email
        auth_result = self.verify_dropbox_token_for_user(auth_flow, auth_code, email)
        if not auth_result:
            return False

        # Extract access token and user_id from the result object
        access_token = auth_result.access_token
        self.user_id = auth_result.user_id

        print(f"Authentication successful.")
        return True

    # Function to verify if the token is valid for the given email
    def verify_dropbox_token_for_user(self, auth_flow, auth_code, expected_email):
        try:
            auth_result = auth_flow.finish(auth_code)
            self.dbx = dropbox.Dropbox(auth_result.access_token)
            current_account = self.dbx.users_get_current_account()
            current_email = current_account.email

            if current_email == expected_email:
                print(f"Token is valid and belongs to {current_email}.")
                return auth_result  # Return the entire auth result
            else:
                print(f"Error: The provided access token belongs to {current_email}, not {expected_email}.")
                return None
        except dropbox.exceptions.AuthError as e:
            print(f"Error: The provided access token is invalid. {e}")
            return None

    # Function to upload a file to Dropbox
    def upload_file(self, file_path, dropbox_dest_path):
        try:
            with open(file_path, "rb") as f:
                self.dbx.files_upload(f.read(), dropbox_dest_path, mute=True)
            print(f"File uploaded successfully to {dropbox_dest_path}.")
        except FileNotFoundError:
            print("The file was not found.")
        except Exception as e:
            print(f"Error: {e}")

    def create_folder(self):
        folder_path = input("Enter folder path: ")
        # Create the folder
        try:
            self.dbx.files_create_folder_v2(folder_path)
            print(f"Folder '{folder_path}' created successfully!")
        except dropbox.exceptions.ApiError as e:
            if e.error.is_path() and e.error.get_path().is_conflict():
                print(f"Folder '{folder_path}' already exists.")
            else:
                print(f"Error creating folder: {e}")

    # Function to list files in the root directory of Dropbox
    def list_files(self):
        try:
            result = self.dbx.files_list_folder('')
            files = result.entries
            if not files:
                print("No files found.")
            else:
                print("Files in your Dropbox account:")
                for file in files:
                    if isinstance(file, dropbox.files.FileMetadata):
                        print(f"File: {file.name} (Size: {file.size} bytes)")
                    else:
                        print(f"Folder: {file.name}")
        except dropbox.exceptions.ApiError as e:
            print(f"Error fetching files: {e}")

    # Function to download a file from Dropbox to the local machine
    def download_file(self, dropbox_file_path):
        try:
            metadata, res = self.dbx.files_download(dropbox_file_path)
            file_name = os.path.basename(dropbox_file_path)
            local_dest_path = os.path.join(os.path.expanduser("~"), "Downloads", file_name)

            with open(local_dest_path, "wb") as f:
                f.write(res.content)

            print(f"File downloaded successfully to {local_dest_path}.")
        except dropbox.exceptions.ApiError as e:
            print(f"Error: {e}")
        except FileNotFoundError:
            print("The specified Dropbox file was not found.")
        except Exception as e:
            print(f"Error: {e}")

    # Function to share a file with an email address (without sending an email)
    def share_file_with_email(self, dropbox_file_path, recipient_email):
        try:
            recipient = dropbox.sharing.MemberSelector.email(recipient_email)
            self.dbx.sharing_add_file_member(dropbox_file_path, [recipient])
            print(f"File successfully shared with {recipient_email}.")
        except dropbox.exceptions.ApiError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Error: {e}")


    def list_shared_files_and_collaborators(self):
        try:
            # Get shared folders metadata
            shared_folders = self.dbx.sharing_list_folders()

            if not shared_folders.entries:
                print("No shared folders found.")
                return

            # Iterate through each shared folder
            for folder in shared_folders.entries:
                print(f"Shared Folder: {folder.name}")

                # List files in the shared folder using the shared folder path
                if not folder.path_lower:
                    print("Folder isn't joined. Joining folder")
                    self.dbx.sharing_mount_folder(folder.shared_folder_id)

                folder_files = self.dbx.files_list_folder(f"/{folder.name}")  # Adjust path for root folders

                for entry in folder_files.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        print(f"  File: {entry.name}")
                        print(f"  Path: {entry.path_display}")

                        # Get file collaborators (who it's shared with)
                        file_members = self.dbx.sharing_list_file_members(entry.id)

                        if file_members.users:
                            for member in file_members.users:
                                print(f"    Shared with: {member.user.email}")
                        else:
                            print(f"    No specific collaborators.")

                print("-" * 40)

        except dropbox.exceptions.ApiError as e:
            print(f"Error occurred: {e}")

    def share_folder(self, folder_path):
        try:
            # Share the folder using the folder path
            shared_folder_metadata = self.dbx.sharing_share_folder(path=folder_path)
            if shared_folder_metadata.is_complete():
                shared_folder_metadata = shared_folder_metadata.get_complete()
            else:
                print(f"Failed to share folder {folder_path}")
                return None
            # If successful, print the shared folder ID and share information
            print(f"Folder '{folder_path}' is now shared.")
            print(f"Shared Folder ID: {shared_folder_metadata.shared_folder_id}")
            return shared_folder_metadata
        except dropbox.exceptions.ApiError as e:
            print(f"Error sharing folder: {e}")
            return None
        
    def add_member_to_share_folder(self, folder_id, email):
        try:
            member = dropbox.sharing.AddMember(dropbox.sharing.MemberSelector.email(email))
            
            # Share the folder with the member (email address)
            result = self.dbx.sharing_add_folder_member(folder_id, [member])
            
            return True
        except dropbox.exceptions.ApiError as e:
            print(f"Error sharing folder '{folder_id}' with {email}: {e}")
            return None
        
    def share_folder_with_member(self, folder_path, email):
        metadata = self.share_folder(folder_path)
        if not metadata:
            print(f"Cannot share folder {folder_path}")
            return
        if not self.add_member_to_share_folder(metadata.shared_folder_id, email):
            print(f"Failed to share folder")
            return
        print(f"Folder shared successfully with {email}!")
    
    def delete_file(self,file_path):
        try:
            response = self.dbx.files_delete_v2(file_path)
            
            print(f"File '{file_path}' has been deleted successfully.")
            return response
        except dropbox.exceptions.ApiError as e:
            print(f"Error deleting file: {e}")
            return None
    def unshare_folder(self, folder_path):
        try:
            shared_folders = self.dbx.sharing_list_folders()
        
            # Check if the folder is shared and find its ID
            shared_folder_id = None
            for folder in shared_folders.entries:
                if folder.path_lower == folder_path.lower():  # Match by folder name
                    shared_folder_id = folder.shared_folder_id
                    break
            
            if not shared_folder_id:
                print(f"Folder '{folder_path}' is not shared or doesn't exist.")
                return
            
            # Step 2: Unshare the folder
            self.dbx.sharing_unshare_folder(shared_folder_id)
            print(f"Folder '{folder_path}' has been unshared.")
            return True
        except dropbox.exceptions.ApiError as e:
            print(f"Error unsharing or deleting folder: {e}")
            return None

# Main function to interact with the user
def main():
    print("Dropbox POC")
    dropbox = DropboxImp()
    #access_token = os.getenv('DROPBOX_TOKEN') if os.getenv('DROPBOX_TOKEN') else authenticate_dropbox()
    email = input("Enter your Dropbox email address: ")
    print(f"Authenticating {email}'s Dropbox account...")
    success = dropbox.authenticate_dropbox(email)
    if not success:
        print("Authentication failed.")
        return

    while True:
        print("\nSelect an action:")
        print("1. List files in Dropbox")
        print("2. Upload a file to Dropbox")
        print("3. Download a file from Dropbox")
        print("4. Share a file from Dropbox with another user")
        print("5. List all shared files")
        print("6. Create new folder")
        print("7. Share folder")
        print("8. Delete file")
        print("9. Unshare folder")
        print("10. Exit")

        choice = input("Enter your choice: ")

        if choice == '1':
            dropbox.list_files()
        elif choice == '2':
            file_path = input("Enter the file path to upload: ")
            dropbox_dest_path = input("Enter the destination path in Dropbox (e.g., /folder/filename): ")
            dropbox.upload_file(file_path, dropbox_dest_path)
        elif choice == '3':
            dropbox_file_path = input("Enter the file path to download (e.g., /folder/filename): ")
            dropbox.download_file(dropbox_file_path)
        elif choice == '4':
            dropbox_file_path = input("Enter the path in Dropbox to share (e.g., /folder/filename): ")
            recipient_email = input("Enter email to share: ")
            dropbox.share_file_with_email(dropbox_file_path, recipient_email)
        elif choice == '5':
            dropbox.list_shared_files_and_collaborators()
        elif choice == '6':
            dropbox.create_folder()
        elif choice == '7':
            dropbox_folder_path = input("Enter the path in Dropbox to share (e.g., /folder/): ")
            recipient_email = input("Enter email to share: ")
            dropbox.share_folder_with_member(dropbox_folder_path,recipient_email)
        elif choice == '8':
            delete_file = input("Enter the file/folder path to delete (e.g., /folder/filename or /folder): ")
            dropbox.delete_file(delete_file)
        elif choice == '9':
            unshare_folder = input("Enter the folder path to unshare (e.g., /folder): ")
            dropbox.unshare_folder(unshare_folder)
        elif choice == '10':
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    main()
