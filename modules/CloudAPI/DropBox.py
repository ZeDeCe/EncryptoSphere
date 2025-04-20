#DropBox POC

import dropbox
import webbrowser
import os 

import dropbox.exceptions 
from CloudService import CloudService
#from utils.DialogBox import input_dialog

DROPBOX_ENCRYPTOSPHERE_ROOT = "TEST"
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
        
        # Create root folder if not already exist
        try:
            self.root_folder = self.create_folder(DROPBOX_ENCRYPTOSPHERE_ROOT, CloudService.Folder("", "", ""))
            print(f"DropBox: Root folder ready")
        except Exception as e:
            print(f"Error: Failed to create root folder: {e}")
            return False
        
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

    def get_children(self, folder : CloudService.Folder) -> list[CloudService.File|CloudService.Folder]:
        """
        Get all file and folder objects that are children of the specified folder
        @param folder the folder object to get the children of
        """
        try:
            result = self.dbx.files_list_folder(folder._id)
            files = []
            while True:
                # Check if the result has more entries
                for entry in result.entries:
                    # Check if the entry is a file or a folder
                    if isinstance(entry, dropbox.files.FileMetadata):
                        files.append(CloudService.File(id=entry.path_lower, name=entry.name, path=entry.path_display))
                    elif isinstance(entry, dropbox.files.FolderMetadata):
                        files.append(CloudService.Folder(id=entry.path_lower, name=entry.name, path=entry.path_display))
                if result.has_more:
                    result = self.dbx.files_list_folder_continue(result.cursor)
                else:
                    break
            return files

        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Error {e}")

    def list_files(self, folder : CloudService.Folder, filter="") -> list[CloudService.File]:
        """
        Function to list files in the root directory of Dropbox
        """
        try:
            result = self.dbx.files_list_folder(folder._id)
            files = []
            while True:
                # Check if the result has more entries
                for entry in result.entries:
                    # Check if the entry is a file or a folder
                    if isinstance(entry, dropbox.files.FileMetadata) and entry.name.startswith(filter):
                        files.append(CloudService.File(id=entry.path_lower, name=entry.name, path=entry.path_display))
                if result.has_more:
                    result = self.dbx.files_list_folder_continue(result.cursor)
                else:
                    break
            return files

        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Error {e}")


    def upload_file(self, data, file_name: str, parent : CloudService.Folder):
        """
        Upload file by path to Dropbox
        """
        path = parent.path
        if not path[0] == "/":
            raise Exception("DropBox: Path is invalid")
        path = f"{path}/{file_name}"

        CHUNK_SIZE = 150 * 1024 * 1024  # 150 MB
        try:
            if len(data) > CHUNK_SIZE:
                id = self.dbx.files_upload_session_start()
                for i in range(0, len(data), CHUNK_SIZE):
                    chunk = data[i:i + CHUNK_SIZE]
                    self.dbx.files_upload_session_append_v2(chunk, dropbox.files.UploadSessionCursor(session_id=id, offset=i))
                self.dbx.files_upload_session_append_v2(data[-(len(data) % (CHUNK_SIZE)):], dropbox.files.UploadSessionCursor(session_id=id, offset=i), True)
                self.dbx.files_upload_session_finish(None, dropbox.files.CommitInfo(path=path, mode=dropbox.files.WriteMode("overwrite")), dropbox.files.UploadSessionCursor(session_id=id))
            else:
                self.dbx.files_upload(data, path, mute=True, mode=dropbox.files.WriteMode("overwrite"))
            print(f"DropBox: {file_name} uploaded successfully.")
            return CloudService.File(id=path.lower(), name=file_name, path=path)
        except Exception as e:
            raise Exception(f"DropBox: Failed to upload file: {e}")
        
    
    def download_file(self, file : CloudService.File): # Changed!
        """
        Download file from Dropbox and return the file's data
        """
        res = None
        try:
            path = file.path
            metadata, res = self.dbx.files_download(path)
            file_data = res.content
            print(f"DropBox: file {path} downloaded successfully.")
            return file_data
        
        except dropbox.exceptions.ApiError as e:
            print(f"DropBox-Error {e}")
            return None
        except FileNotFoundError:
            print("DropBox: The specified Dropbox file was not found.")
            return None
        except Exception as e:
            raise Exception(f"DropBox-Error: {e}")
        finally:
            if res:
                res.close()


    def delete_file(self, file : CloudService.File): # Changed!
        """
        Delete file from DropBox by name
        """
        try:
            path = file.path
            self.dbx.files_delete_v2(path)
            print(f"DropBox: {path} deleted successfully.")
            return True
        except dropbox.exceptions.ApiError as e:
            raise Exception(f"DropBox-Error deleting file: {e}")
        
    def get_session_folder(self, name : str) -> CloudService.Folder:
        children = self.get_children(self.root_folder)
        for child in children:
            if child.name == name:
                return child
        return self.create_folder(name, self.root_folder)

    # def get_folder(self, folder_path : str) -> CloudService.Folder:
    #     """
    #     Get folder object
    #     """
    #     try:
    #         if folder_path == "/":
    #             print("Error: Cannot get root folder.")
    #             return None
            
    #         metadata = self.dbx.files_get_metadata(folder_path)
    #         print(metadata)
    #         # Ensure it's a folder, not a file
    #         if isinstance(metadata, dropbox.files.FolderMetadata):
    #             folder_path = metadata.path_display
    #             if metadata.shared_folder_id:
    #                 folder_id = metadata.shared_folder_id
    #                 shared = True
    #                 folder_obj = CloudService.Folder(id=folder_id, path=folder_path, shared=True, members_shared=None)
    #                 members_shared = self.get_members_shared(folder_obj)
    #                 folder_obj.members_shared = members_shared
    #                 return folder_obj
    #             else:
    #                 folder_obj = CloudService.Folder(id=metadata.id, path=folder_path, shared=False, members_shared=None)
    #                 return folder_obj
    #         else:
    #             print(f"Error: {folder_path} is not a folder.")
    #             return None
        
    #     except dropbox.exceptions.ApiError as e:
    #         raise Exception(f"Error: {e}")

    def create_folder(self, name, parent) -> CloudService.Folder:
        """
        Create folder on DropBox and return its path
        """
        path = f"{parent.path}/{name}"
        try:
            new_folder = self.dbx.files_create_folder_v2(path)
            new_folder = new_folder.metadata
            return CloudService.Folder(new_folder.path_lower, new_folder.path_display, new_folder.name, False)

        except dropbox.exceptions.ApiError as e:
            # Folder already exists
            if e.error.is_path() and e.error.get_path().is_conflict():
                f = self.dbx.files_get_metadata(path)
                if f.shared_folder_id:
                    obj = CloudService.Folder(id=f.shared_folder_id, path=f.path_display, shared=True)
                    return obj
                return CloudService.Folder(id=f.path_lower, path=f.path_display, shared=False)
            else:
                raise Exception(f"Error: {e}")


    def create_shared_session(self, name, emails):
        try:
            folder = self.create_folder(name, self.root_folder) # folder is CloudService.Folder object
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
            id = folder._id
            if shared_members == False:
                metadata = self._share_folder(folder._id)
                if not metadata:
                    raise Exception(f"Dropbox: Failed to share folder {folder.path}")
                id = metadata.shared_folder_id

            shared_members = [] if shared_members == False else shared_members
            # Add all members
            to_add = [member for member in emails if not member in shared_members]
            for email in to_add:
                if not self._add_member_to_share_folder(id, email):
                    print(f"Failed to share folder")
                    return None
                print(f"Folder shared successfully with {email}!")
            return CloudService.Folder(id=id, path=folder.path, name=folder.name, shared=True)
        
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
        id = folder._id
        if not folder.shared:
            raise Exception("Error: Folder ID should be a shared ID")
        try:
            self.dbx.sharing_unshare_folder(id) # TODO: delete folder from dropbox
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
        folder_id = folder._id
        if not folder.shared:
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
    

    def list_shared_folders(self, filter="") -> list[CloudService.Folder]:
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
                if not folder.name.endswith("_ENCRYPTOSPHERE_SHARE"):
                    continue
                if not folder.path_lower:
                    print(f"Folder {folder.name} isn't joined. Attempting to join folder...")
                    try:
                        folder = self.dbx.sharing_mount_folder(folder.shared_folder_id)

                    except dropbox.exceptions.ApiError as e:
                        print(f"Failed to mount folder {folder.name}: {e}")
                        continue  # Skip this folder if we can't mount it
                
                folder_path = folder.path_display if folder.path_display else None
                obj = CloudService.Folder(id=folder.shared_folder_id, path=folder_path, shared=True)
                shared_folders_info.append(obj)

            return shared_folders_info

        except dropbox.exceptions.ApiError as e:
            print(f"Error occurred: {e}")
    
    def get_members_shared(self, folder : CloudService.Folder):
        """
        Returns a list of emails that the folder is shared with if shared, and false if not shared
        @param folder the folder object
        """
        if not folder.shared:
            return False
        try:
            # metadata = self.dbx.files_get_metadata(folder._id)

            # if isinstance(metadata, dropbox.files.FolderMetadata) and metadata.shared_folder_id:
            #     folder_id = metadata.shared_folder_id
            # else:
            #     print(f"Folder '{folder}' is not a shared folder.")
            #     return False
            
            members = self.dbx.sharing_list_folder_members(folder._id)
            members_list = []

            for member in members.users:
                members_list.append(member.user.email)

            return members_list
        except dropbox.exceptions.ApiError as e:
            raise Exception(f"Cannot access folder because not a member")

    def get_name(self):
        return "D"


# Unit Test, make sure to enter email!
'''
import customtkinter as ctk
def input_dialog(title, text):
    # Create the input dialog
    dialog = ctk.CTkInputDialog(text=text, title=title)
    
    # Update idletasks to calculate the window's size
    dialog.update_idletasks()
    
    # Get screen dimensions
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    
    # Get the dialog's current size
    dialog_width = dialog.winfo_width()
    dialog_height = dialog.winfo_height()
    
    # Calculate the position to center the dialog on the screen
    position_top = (screen_height // 2) - (dialog_height // 2)
    position_left = (screen_width // 2) - (dialog_width // 2)
    
    # Set the position without altering the size
    dialog.geometry(f"+{position_left}+{position_top}")
    
    # Ensure the dialog stays on top
    dialog.attributes("-topmost", True)
    
    # Return the input received from the dialog
    return dialog.get_input()

def test():
    """
    Test function for DropBox
    """
    dbx = DropBox("EMAIL HERE")
    dbx.authenticate_cloud()
    folder = dbx.get_session_folder("test")
    print(dbx.get_children(folder))
    download = dbx.upload_file(b"Content","Test1", folder)
    delete = dbx.upload_file(b"Special", "$Special", folder)
    print("All files:")
    print(dbx.list_files(folder))
    print("Special files:")
    print(dbx.list_files(folder, "$"))
    dbx.create_folder("folder1", folder)
    shared = dbx.create_shared_session("shared!", ["demek14150@sfxeur.com"])
    download2 = dbx.upload_file(b"Content shared","Test2", shared)
    print(dbx.download_file(download))
    print(dbx.download_file(download2))
    dbx.delete_file(delete)
    print("Members:")
    print(dbx.get_members_shared(shared))
    dbx.unshare_by_email(shared, ["demek14150@sfxeur.com"])
    print(dbx.get_members_shared(shared))
    dbx.unshare_folder(shared)
    print("Done")

    

if __name__ == "__main__":
    test()
'''