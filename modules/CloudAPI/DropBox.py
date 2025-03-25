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
        """
        Function to authenticate the Dropbox account and get access token
        The function recives an email address to authenticate to, and call verify_dropbox_token_for_user to verify the authentication
        The function creates and save the root folder (if not already exsist)
        """
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
        auth_result = self._verify_dropbox_token_for_user(auth_flow, auth_code, self.email)
        if not auth_result:
            return False
        
        # Extract access token and user_id from the result object
        access_token = auth_result.access_token
        self.user_id = auth_result.user_id
        self.authenticated = True
        return True

    def _verify_dropbox_token_for_user(self, auth_flow, auth_code, expected_email):
        """
        Function to verify if the token is valid for the given email
        """
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
            raise Exception(f"Error {e}")

    def list_files(self, folder='/'):
        """
        Function to list files in the root directory of Dropbox
        """
        try:
            result = self.dbx.files_list_folder(folder)
            file_names = [entry.name for entry in result.entries]
            # No files found
            if not file_names:
                return None
            
            else: 
                return file_names
        
        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Error {e}")

    def upload_file(self, data, file_name: str, path="/"):
        """
        Upload file by path to Dropbox
        """
        if not path[0] == "/":
            raise Exception("DropBox: Path is invalid")
        path = f"{path}/{file_name}"

        try:
            self.dbx.files_upload(data, path, mute=True, mode=dropbox.files.WriteMode("overwrite"))
            print(f"File uploaded successfully to {path}.")
            return True
        except Exception as e:
            raise Exception(f"DropBox: Failed to upload file: {e}")
        
    
    def download_file(self, file_name: str, path="/"):
        """
        Download file from Dropbox and return the file's data
        """
        try:
            path = f"{path}/{file_name}"
            metadata, res = self.dbx.files_download(path)
            file_data = res.content
            print(f"File data downloaded successfully.")
            return file_data
        
        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Error {e}")
        except FileNotFoundError:
             raise Exception("The specified Dropbox file was not found.")
        except Exception as e:
            raise Exception(f"Error: {e}")


    def delete_file(self, file_name: str, path: str):
        """
        Delete file from DropBox by name
        """
        try:
            path = f"{path}/{file_name}"
            self.dbx.files_delete_v2(path)
            print(f"File '{file_name}' has been deleted successfully.")
            return True
        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Error deleting file: {e}")


    def get_folder(self, folder_path : str) -> any:
        """
        Get folder object
        """
        try:
            metadata = self.dbx.files_get_metadata(folder_path)
            
            # Ensure it's a folder, not a file
            if isinstance(metadata, dropbox.files.FolderMetadata):
                return metadata.path_display
            
            else:
                print(f"Error: {folder_path} is not a folder.")
                return None
        
        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Error: {e}")

    def get_folder_path(self, folder):
        """
        Returns the folder path of a given folder object (as recived from get_folder())
        """
        folder_path = self.get_folder(folder)
        if folder_path:
            return folder_path
        else: 
            return None

    def create_folder(self, folder_path):
        """
        Create folder on DropBox and return its path
        """
        try:
            new_folder = self.dbx.files_create_folder_v2(folder_path)
            return new_folder.metadata.path_display

        except dropbox.exceptions.ApiError as e:
            # Folder already exists
            if e.error.is_path() and e.error.get_path().is_conflict():
                exsist_folder = self.dbx.files_get_metadata(folder_path)
                return exsist_folder.path_display
            else:
                raise Exception(f"Error: {e}")


    def create_shared_folder(self, folder_path, emails):
        try:
            folder = self.create_folder(folder_path)
            return self.share_folder(folder, emails)
        except dropbox.exceptions.ApiError as e:
            print(f"Error occurred: {e}")

    def _share_folder(self, folder_path):
        """
        Protected function to share folder
        """
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
            return shared_folder_metadata.path_display
        except dropbox.exceptions.ApiError as e:
            print(f"Error sharing folder: {e}")
            return None
        
    def _add_member_to_share_folder(self, folder_id, email):
        """
        Protected function to share a folder by email address
        """
        try:
            member = dropbox.sharing.AddMember(dropbox.sharing.MemberSelector.email(email))
            
            # Share the folder with the member (email address)
            result = self.dbx.sharing_add_folder_member(folder_id, [member])
            
            return True
        except dropbox.exceptions.ApiError as e:
            print(f"Error sharing folder '{folder_id}' with {email}: {e}")
            return None
        
    def share_folder(self, folder_path : str, emails : list[str]):
        """
        Share a folder on DropBox
        """
        try:
            metadata = self._share_folder(folder_path)
            if not metadata:
                print(f"Cannot share folder {folder_path}")
                return None
        
            for email in emails:
                if not self._add_member_to_share_folder(metadata.shared_folder_id, email):
                    print(f"Failed to share folder")
                    return None
                print(f"Folder shared successfully with {email}!")
            return metadata #file path
        
        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Error: {e}")
    
    
    def unshare_folder(self, folder_name):
        """
        Unshare a folder on DropBox
        """
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
                return False
            
            # Step 2: Unshare the folder
            self.dbx.sharing_unshare_folder(shared_folder_id)
            print(f"Folder '{folder_name}' has been unshared.")
            return True
        except dropbox.exceptions.ApiError as e:
             raise Exception(f"Error unsharing or deleting folder: {e}")

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
        
    def unshare_by_email(self, folder, emails):
        """
        Unshare a folder by given email address
        """
        for email in emails:
            try:
                # Select the member using their email address
                member = dropbox.sharing.MemberSelector.email(email)  
                # Remove the member from the shared folder
                result = self.dbx.sharing_remove_folder_member(folder, [member])  
                print(f"Member {email} removed from folder '{folder}' successfully.")
            except dropbox.exceptions.ApiError as e:
                raise Exception(f"Error removing member '{email}' from folder '{folder}': {e}")
        return True
    
    def list_shared_files(self, folder=None):
        """
        List all shared files and folders in the cloud storage
        @param folder, optional, the folder object to look into
        @return a list of shared file names
        """
        pass

    def list_shared_folders(self):
        """
        Function to list all shared folders
        """
        shared_folders_info = []
        try:
            # Get shared folders metadata
            shared_folders = self.dbx.sharing_list_folders()

            if not shared_folders.entries:
                print("No shared folders found.")
                return None

            # Iterate through each shared folder
            for folder in shared_folders.entries:
                folder_info = {
                    "folder_name": folder.name,
                    "folder_id": folder.shared_folder_id,
                    "folder_path": folder.path_display if folder.path_display else "No Path",
                    "files": []
                }

                # List files in the shared folder using the shared folder path
                if not folder.path_lower:
                    print("Folder isn't joined. Joining folder")
                    self.dbx.sharing_mount_folder(folder.shared_folder_id)

                folder_files = self.dbx.files_list_folder(f"/{folder.name}")  # Adjust path for root folders

                for entry in folder_files.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        file_info = {
                            "file_name": entry.name,
                            "file_path": entry.path_display,
                            "file_id": entry.id,
                            "collaborators": []
                        }
                        # Get file collaborators (who it's shared with)
                        file_members = self.dbx.sharing_list_file_members(entry.id)

                        if file_members.users:
                            for member in file_members.users:
                                file_info["collaborators"].append(member.user.email)
                        else:
                            file_info["collaborators"].append("No specific collaborators")

                        folder_info["files"].append(file_info)
                    
                    shared_folders_info.append(folder_info)

                return shared_folders_info

        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Error occurred: {e}")

    def get_members_shared(self, folder : any):
        """
        Returns a list of emails that the folder is shared with if shared, and false if not shared
        @param folder the folder object
        """
        pass

    def get_name(self):
        return "D"

'''
# Main function to interact with the user
def main():
    print("Dropbox POC")
    #access_token = os.getenv('DROPBOX_TOKEN') if os.getenv('DROPBOX_TOKEN') else authenticate_dropbox()
    email = input("Enter your Dropbox email address: ")
    print(f"Authenticating {email}'s Dropbox account...")
    dropbox = DropBox(email)
    success = dropbox.authenticate(email)
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