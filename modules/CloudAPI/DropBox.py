#DropBox POC

import dropbox
import webbrowser
import os 

import dropbox.exceptions 
from modules.CloudAPI.CloudService import CloudService
from utils.DialogBox import input_dialog


DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")

class DropBox(CloudService):
    # Function to authenticate the Dropbox account and get access token
    # The function recives an email address to authenticate to, and call verify_dropbox_token_for_user to verify the authentication
    # The function creates and save the root folder (if not already exsist)
    def authenticate_cloud(self):
        if super().authenticate_cloud():
            return True
        # Start the OAuth flow
        auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(DROPBOX_APP_KEY, DROPBOX_APP_SECRET)
        # Generate the authorization URL
        auth_url = auth_flow.start()
        # Automatically open the URL in the default browser
        webbrowser.open(auth_url)
        # Get the authorization code from the user
        auth_code = input_dialog("DropBox Authentication", f"Browse to {auth_url} and insert here your dropbox access code" )
        # Verify if the token is valid for the given email
        auth_result = self.verify_dropbox_token_for_user(auth_flow, auth_code, self.email)
        if not auth_result:
            return False
        # Extract access token and user_id from the result object
        access_token = auth_result.access_token
        self.user_id = auth_result.user_id
        self.authenticated = True
        return True

    # Function to verify if the token is valid for the given email
    def verify_dropbox_token_for_user(self, auth_flow, auth_code, expected_email):
        try:
            auth_result = auth_flow.finish(auth_code)
            self.dbx = dropbox.Dropbox(auth_result.access_token)
            current_account = self.dbx.users_get_current_account()
            current_email = current_account.email

            # Authentication succeded
            if current_email == expected_email:
                return auth_result  # Return the entire auth result
            # Athentication failed
            else:
                return None
        except dropbox.exceptions.AuthError as e:
            print(f"Error {e}")
            return None

    def upload_file(self, data, file_name: str, path="/"):
        if not path[0] == "/":
            raise Exception("DropBox: Path is invalid")
        path = f"{path}/{file_name}"

        try:
            self.dbx.files_upload(data, path, mute=True)
            print(f"File uploaded successfully to {path}.")
        except Exception as e:
            raise Exception(f"DropBox: Failed to upload file: {e}")

    # Create folder on DropBox
    def create_folder(self, folder_path):
        try:
            result = self.dbx.files_create_folder_v2(folder_path)
            id = result.metadata.id
            return folder_path
        except dropbox.exceptions.ApiError as e:
            # Folder already exists
            if e.error.is_path() and e.error.get_path().is_conflict():
                id = self.dbx.files_get_metadata(folder_path).id
                return folder_path
            else:
                print(f"Error {e}")
                return None

    # TODO: Implement
    def get_folder(self, folder_path : str) -> any:
        pass

    # TODO implement
    def get_members_shared(self, folder_path : str) -> dict[str] | bool:
        return False

    # Function to list files in the root directory of Dropbox
    def list_files(self):
        file_names = []
        try:
            result = self.dbx.files_list_folder('')
            files = result.entries
            # No files found
            if not files:
                return file_names
            else:
                for file in files:
                    '''
                    if isinstance(file, dropbox.files.FileMetadata):
                        print(f"File: {file.name} (Size: {file.size} bytes)")
                    else:
                        print(f"Folder: {file.name}")
                    '''
                    file_names.append(file.name)
                return file_names
        except dropbox.exceptions.ApiError as e:
            print(f"Error {e}")
            return None

    # TODO: refactor this function to match cloudservice!
    def download_file(self, file_name, path):
        try:
            metadata, res = self.dbx.files_download(file_name)
            dropbox_file_path = os.path.basename(file_name)
            local_dest_path = os.path.join(os.path.expanduser("~"), "Downloads", dropbox_file_path)

            with open(local_dest_path, "wb") as f:
                f.write(res.content)

            print(f"File downloaded successfully to {local_dest_path}.")
        except dropbox.exceptions.ApiError as e:
            print(f"Error: {e}")
        except FileNotFoundError:
            print("The specified Dropbox file was not found.")
        except Exception as e:
            print(f"Error: {e}")

    '''
    # Function to share a file with an email address (without sending an email), as of now - uneccacery 
    def share_file_with_email(self, dropbox_file_path, recipient_email):
        try:
            recipient = dropbox.sharing.MemberSelector.email(recipient_email)
            self.dbx.sharing_add_file_member(dropbox_file_path, [recipient])
            print(f"File successfully shared with {recipient_email}.")
        except dropbox.exceptions.ApiError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Error: {e}")
    '''
    # Function to list all shared files and folders
    # Need to change the return value instead of prints
    def list_shared_files(self):
        try:
            # Get shared folders metadata
            shared_folders = self.dbx.sharing_list_folders()

            if not shared_folders.entries:
                print("No shared folders found.")
                return None

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
                        print(f"File: {entry.name}")
                        print(f"Path: {entry.path_display}")

                        # Get file collaborators (who it's shared with)
                        file_members = self.dbx.sharing_list_file_members(entry.id)

                        if file_members.users:
                            for member in file_members.users:
                                print(f"Shared with: {member.user.email}")
                        else:
                            print(f"No specific collaborators.")

                print("-" * 40)

        except dropbox.exceptions.ApiError as e:
            print(f"Error occurred: {e}")


    def create_shared_folder(self, folder_path, emails):
        try:
            folder = self.create_folder(folder_path)
            return self.share(folder, emails)
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
        
    def share(self, folder_path : str, emails : list[str]):
        metadata = self.share_folder(folder_path)
        if not metadata:
            print(f"Cannot share folder {folder_path}")
            return
        for email in emails:
            if not self.add_member_to_share_folder(metadata.shared_folder_id, email):
                print(f"Failed to share folder")
                return
            print(f"Folder shared successfully with {email}!")
        return folder_path
    
    def delete_file(self, file_name):
        try:
            response = self.dbx.files_delete_v2(file_name)
            print(f"File '{file_name}' has been deleted successfully.")
            return response
        except dropbox.exceptions.ApiError as e:
            print(f"Error deleting file: {e}")
            return None

        
    def unshare_folder(self, folder_name):
        try:
            shared_folders = self.dbx.sharing_list_folders()
        
            # Check if the folder is shared and find its ID
            shared_folder_id = None
            for folder in shared_folders.entries:
                if folder.path_lower == folder_name.lower():  # Match by folder name
                    shared_folder_id = folder.shared_folder_id
                    break
            
            if not shared_folder_id:
                print(f"Folder '{folder_name}' is not shared or doesn't exist.")
                return None
            
            # Step 2: Unshare the folder
            self.dbx.sharing_unshare_folder(shared_folder_id)
            print(f"Folder '{folder_name}' has been unshared.")
            return True
        except dropbox.exceptions.ApiError as e:
            print(f"Error unsharing or deleting folder: {e}")
            return None
        
    def unshare_by_email(self, folder, emails):
        for email in emails:
            try:
                # Select the member using their email address
                member = dropbox.sharing.MemberSelector.email(email)  
                # Remove the member from the shared folder
                result = self.dbx.sharing_remove_folder_member(folder, [member])  
                print(f"Member {email} removed from folder '{folder}' successfully.")
            except dropbox.exceptions.ApiError as e:
                print(f"Error removing member '{email}' from folder '{folder}': {e}")
                return None
        return True
    
    def get_folder_path(self, folder):
        pass

    def list_shared_folders(self):
        pass

    def get_name(self):
        return "D"

'''    
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
        elif choice == '5':
            dropbox.list_shared_files()
        elif choice == '6':
            dropbox.create_folder()
        elif choice == '7':
            dropbox_folder_path = input("Enter the path in Dropbox to share (e.g., /folder/): ")
            recipient_email = input("Enter email to share: ")
            dropbox.share(dropbox_folder_path,recipient_email)
        elif choice == '8':
            delete_file = input("Enter the file/folder path to delete (e.g., /folder/filename or /folder): ")
            dropbox.delete_file(delete_file)
        elif choice == '9':
            unshare_folder = input("Enter the folder path to unshare (e.g., /folder): ")
            dropbox.unshare(unshare_folder)
        elif choice == '10':
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    main()
'''