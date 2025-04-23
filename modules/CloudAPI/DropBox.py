#DropBox POC

import dropbox
import webbrowser
import os
import json

import dropbox.exceptions 
from modules.CloudAPI.CloudService import CloudService
from utils.DialogBox import input_dialog


DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
DROPBOX_TOKEN_PATH = "dropbox_token.json"

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
        
        # Check for an existing token file
        if os.path.exists(DROPBOX_TOKEN_PATH):
            try:
                with open(DROPBOX_TOKEN_PATH, "r") as token_file:
                    print("DropBox  : Loading existing Dropbox token...")
                    # Load the token from the JSON file
                    token_data = json.load(token_file)
                    access_token = token_data.get("access_token")
                    self.dbx = dropbox.Dropbox(access_token)
                    
                    # Verify the stored token email matches the current user
                    current_email = self.dbx.users_get_current_account().email
                    if current_email == self.email:
                        self.authenticated = True
                        self.user_id = self.dbx.users_get_current_account().account_id
                        return True
                    else:
                        print("DropBox  : Email mismatch with stored Dropbox token.")
            except Exception as e:
                print(f"DropBox  : Error loading or validating Dropbox token: {e}")
        
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
        
        # Save the token to a JSON file for future use
        self._save_dropbox_token_to_json(auth_result.access_token)
        
        # Extract access token and user_id from the result object
        access_token = auth_result.access_token
        self.user_id = auth_result.user_id
        self.authenticated = True
        return True
    
    def _save_dropbox_token_to_json(self, access_token):
        """
        Save the Dropbox access token to a JSON file.
        """
        try:
            token_data = {
                "access_token": access_token
            }
            with open(DROPBOX_TOKEN_PATH, "w") as token_file:
                json.dump(token_data, token_file)
            print("Dropbox token saved successfully.")
        except Exception as e:
            print(f"Error saving Dropbox token: {e}")

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
            # override if exsist
            self.dbx.files_upload(data, path, mute=True, mode=dropbox.files.WriteMode("overwrite"))
            print(f"DropBox     : {file_name} uploaded successfully.")
            return True
        except Exception as e:
            raise Exception(f"DropBox     : Failed to upload file: {e}")
        
    
    def download_file(self, file_name: str, path="/"):
        """
        Download file from Dropbox and return the file's data
        """
        try:
            path = f"{path}/{file_name}"
            metadata, res = self.dbx.files_download(path)
            file_data = res.content
            print(f"DropBox     : file {path} downloaded successfully.")
            return file_data
        
        except dropbox.exceptions.ApiError as e:
            print(f"DropBox-Error {e}")
            return None
        except FileNotFoundError:
            print("DropBox: The specified Dropbox file was not found.")
            return None
        except Exception as e:
            print(f"DropBox-Error: {e}")
            return None


    def delete_file(self, file_name: str, path: str):
        """
        Delete file from DropBox by name
        """
        try:
            path = f"{path}/{file_name}"
            self.dbx.files_delete_v2(path)
            print(f"DropBox     : {file_name} deleted successfully.")
            return True
        except dropbox.exceptions.ApiError as e:
            raise Exception(f"DropBox-Error deleting file: {e}")


    def get_folder(self, folder_path : str) -> CloudService.Folder:
        """
        Get folder object
        """
        try:
            if folder_path == "/":
                print("Error: Cannot get root folder.")
                return None
            
            metadata = self.dbx.files_get_metadata(folder_path)
            print(metadata)
            # Ensure it's a folder, not a file
            if isinstance(metadata, dropbox.files.FolderMetadata):
                folder_path = metadata.path_display
                if metadata.shared_folder_id:
                    folder_id = metadata.shared_folder_id
                    shared = True
                    folder_obj = CloudService.Folder(id=folder_id, path=folder_path, shared=True, members_shared=None)
                    members_shared = self.get_members_shared(folder_obj)
                    folder_obj.members_shared = members_shared
                    return folder_obj
                else:
                    folder_obj = CloudService.Folder(id=metadata.id, path=folder_path, shared=False, members_shared=None)
                    return folder_obj
            else:
                print(f"Error: {folder_path} is not a folder.")
                return None
        
        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Error: {e}")

    def get_folder_path(self, folder: CloudService.Folder) -> str:
        """
        Returns the folder path of a given folder object (as recived from get_folder())
        """
        folder_path = folder.path
        if folder_path:
            return folder_path
        else: 
            return None

    def create_folder(self, folder_path: str) -> CloudService.Folder:
        """
        Create folder on DropBox and return its path
        """
        try:
            new_folder = self.dbx.files_create_folder_v2(folder_path)
            new_folder = new_folder.metadata
            return CloudService.Folder(id=new_folder.id, path=new_folder.path_display, shared=False, members_shared=None)

        except dropbox.exceptions.ApiError as e:
            # Folder already exists
            if e.error.is_path() and e.error.get_path().is_conflict():
                f = self.dbx.files_get_metadata(folder_path)
                print(f)
                if f.shared_folder_id:
                    obj = CloudService.Folder(id=f.shared_folder_id, path=f.path_display, shared=True, members_shared=None)
                    members_shared = self.get_members_shared(obj)
                    obj.members_shared = members_shared
                    return obj
                return CloudService.Folder(id=f.id, path=f.path_display)
            else:
                raise Exception(f"Error: {e}")


    def create_shared_folder(self, folder_path, emails):
        try:
            folder = self.create_folder(folder_path) # folder is CloudService.Folder object
            return self.share_folder(folder, emails)
        except dropbox.exceptions.ApiError as e:
            print(f"Dropbox Error occurred: {e}")
        except Exception as e:
            print(f"Error occurred: {e}")
        return None

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
            return shared_folder_metadata
        except dropbox.exceptions.ApiError as e:
            print(f"Error sharing folder: {e}")
            return None
        
    def _add_member_to_share_folder(self, folder_id, email):
        """
        Protected function to share a folder by email address
        """
        try:
            member = dropbox.sharing.AddMember(dropbox.sharing.MemberSelector.email(email), dropbox.sharing.AccessLevel.editor)
            
            # Share the folder with the member (email address)
            result = self.dbx.sharing_add_folder_member(folder_id, [member])
            
            return True
        except dropbox.exceptions.ApiError as e:
            print(f"Error sharing folder '{folder_id}' with {email}: {e}")
            return None
        
    def share_folder(self, folder : CloudService.Folder, emails : list[str]) -> CloudService.Folder:
        """
        Share a folder on DropBox
        """
        try:
            # Check if the folder is already shared
            shared_members = self.get_members_shared(folder)
            if shared_members:
                print(f"Folder '{folder.path}' is already shared! with: {shared_members}")
                # Optionally, add new members to the existing shared folder
                for email in emails:
                    if email not in shared_members:
                        if not self._add_member_to_share_folder(self._get_shared_folder_from_path(folder.path), email):
                            print(f"Failed to add {email} to the shared folder")
                            return None
                        print(f"Folder shared successfully with {email}!")
                return self.get_folder(folder.path)  #return the folder object

            metadata = self._share_folder(folder.path)
            if not metadata:
                print(f"Cannot share folder {folder.path}")
                return None
        
            for email in emails:
                if not self._add_member_to_share_folder(metadata.shared_folder_id, email):
                    print(f"Failed to share folder")
                    return None
                print(f"Folder shared successfully with {email}!")
            return CloudService.Folder(id=metadata.shared_folder_id, path=metadata.path_display, shared=True, members_shared=emails)
        
        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Error: {e}")
    
    
    def _get_shared_folder_from_path(self, path):
        shared_folders = self.dbx.sharing_list_folders()
        shared_folder_id = None
        for folder in shared_folders.entries:
            if folder.path_lower == path.lower():  # Match by folder name
                shared_folder_id = folder.shared_folder_id
                break
        
        if not shared_folder_id:
            print(f"Folder '{path}' is not shared or doesn't exist.")
            return None
        return shared_folder_id

    def unshare_folder(self, folder : CloudService.Folder):
        """
        Unshare a folder on DropBox
        """
        id = folder.id
        if isinstance(id, str):
            raise Exception("Error: Folder ID should be a shared ID")
        try:
            self.dbx.sharing_unshare_folder(id)
            print(f"Folder '{folder.path}' has been unshared.")
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
        
    def unshare_by_email(self, folder : CloudService.Folder, emails):
        """
        Unshare a folder by given email address
        """
        folder_id = folder.id
        if isinstance(folder_id, str):
            raise Exception("Error: Folder ID should be a shared ID")
        success = True
        for email in emails:
            try:
                # Select the member using their email address
                member = dropbox.sharing.MemberSelector.email(email) 

                # Remove the member from the shared folder
                result = self.dbx.sharing_remove_folder_member(folder_id, member, False)  
                print(f"Member {email} removed from folder '{folder}' successfully.")
            except dropbox.exceptions.ApiError as e:
                print(f"Error removing member '{email}' from folder '{folder}': {e}")
                success = False
                continue
        return success
    
    def list_shared_files(self, folder=None):
        """
        List all shared files and folders in the cloud storage
        @param folder, optional, the folder object to look into
        @return a list of shared file names
        """
        pass

    def list_shared_folders(self) -> list[CloudService.Folder]:
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
                # Check if the folder has a valid path or is already mounted
                if not folder.path_lower:
                    print(f"Folder {folder.name} isn't joined. Attempting to join folder...")
                    try:
                        folder = self.dbx.sharing_mount_folder(folder.shared_folder_id)

                    except dropbox.exceptions.ApiError as e:
                        print(f"Failed to mount folder {folder.name}: {e}")
                        continue  # Skip this folder if we can't mount it
                
                folder_path = folder.path_display if folder.path_display else None
                obj = CloudService.Folder(id=folder.shared_folder_id, path=folder_path, shared=True, members_shared=None)
                members_shared = self.get_members_shared(obj)
                obj.members_shared = members_shared
                shared_folders_info.append(obj)

            return shared_folders_info

        except dropbox.exceptions.ApiError as e:
            print(f"Error occurred: {e}")
    
    def get_members_shared(self, folder : CloudService.Folder):
        """
        Returns a list of emails that the folder is shared with if shared, and false if not shared
        @param folder the folder object
        """
        try:
            metadata = self.dbx.files_get_metadata(folder.path)

            if isinstance(metadata, dropbox.files.FolderMetadata) and metadata.shared_folder_id:
                folder_id = metadata.shared_folder_id
            else:
                print(f"Folder '{folder}' is not a shared folder.")
                return False
            
            members = self.dbx.sharing_list_folder_members(folder_id)
            members_list = []

            for member in members.users:
                members_list.append(member.user.email)

            return members_list

        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Dropbox API error: {e}")

    def get_name(self):
        return "D"
