import os
import io
from dotenv import load_dotenv
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.auth.transport.requests import Request
from modules.CloudAPI.CloudService import CloudService

load_dotenv()
# Set up Google Drive API
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
API_KEY = os.getenv("GOOGLE_API_KEY")
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']

class GoogleDrive(CloudService):
    def __new__(cls, email: str):
            """
            Makes all child objects with the same email a singleton.
            """
            if not hasattr(cls, 'instances'):
                cls.instances = {}
            
            # Use super().__new__ with the email parameter
            single = cls.instances.get(email)
            if single:
                return single
            
            # Pass the email when creating a new instance
            cls.instances[email] = super().__new__(cls, email)
            cls.instances[email].authenticated = False
            cls.instances[email].email = email
            cls.instances[email].drive_service = None
            return cls.instances[email]

    def __init__(self, email: str):
        """
        Initialization method 
        """
        super().__init__(email)  # Call parent __init__
        
        # If not authenticated, try to authenticate
        if not self.authenticated:
            self.authenticate_cloud()

    def authenticate_cloud(self):
        """
        Authenticate with Google Drive
        """
        # First check if already authenticated
        if self.authenticated:
            return True

        try:
            # Let the user log in and obtain new credentials every time
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=0)
            
            self.drive_service = build('drive', 'v3', credentials=creds)
            
            # Verify the email matches
            user_info = self.drive_service.about().get(fields="user").execute()
            if user_info['user']['emailAddress'] == self.email:
                self.authenticated = True
                return True
            else:
                print("Email mismatch during authentication")
                return False
        
        except HttpError as error:
            print(f"An error occurred: {error}")
            return False


    def list_files(self, folder='/'):
        """
        List files in Google Drive
        """
        try:
            all_files = []
            page_token = None
            
            # Get all files with pagination
            while True:
                results = self.drive_service.files().list(
                    pageSize=100,
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageToken=page_token
                ).execute()
                
                items = results.get('files', [])
                all_files.extend([item['name'] for item in items])
                page_token = results.get('nextPageToken')
                
                if not page_token:
                    break
            
            return all_files
        
        except HttpError as error:
            raise Exception(f"Error listing files: {error}")

    def upload_file(self, data: bytes, file_name: str, path: str):
        try:
            if not data:
                raise ValueError("Error: File data is empty")

            if not path.startswith("/"):
                raise ValueError("Google Drive: Path is invalid, must start with '/'")

            file_metadata = {
                'name': file_name,
                'parents': [path] if path != "/" else []  
            }

            media = MediaIoBaseUpload(io.BytesIO(data), mimetype='application/octet-stream')

            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

            print(f"File uploaded successfully to {path}/{file_name}")
            return True
        
        except HttpError as error:
            raise Exception(f"Google Drive: Upload failed - {error}")
        except Exception as error:
            raise Exception(f"Unexpected error during upload: {error}")

    def download_file(self, file_name: str, path: str):
        """
        Download a file from Google Drive
        @param file_name: the name of the file to download
        @param path: the path where the file will be saved (for Dropbox compatibility, not used here)
        @return: file content (bytes)
        """
        try:
            results = self.drive_service.files().list(
                q=f"name = '{file_name}'",
                fields="files(id, name, mimeType)"
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                raise Exception(f"File {file_name} not found in Google Drive")
            
            file_id = files[0]['id']
            mime_type = files[0].get('mimeType', '')
            
            if mime_type.startswith('application/vnd.google-apps'):
                request = self.drive_service.files().export_media(
                    fileId=file_id,
                    mimeType='application/pdf'  
                )
            else:
                request = self.drive_service.files().get_media(fileId=file_id)
            
            return request.execute()  
        except HttpError as error:
            raise Exception(f"Error downloading file from Google Drive: {error}")

    
    def delete_file(self, file_name: str, path: str = '') -> bool:
        """
        Delete a file from Google Drive
        """
        try:
            # Search file by name
            results = self.drive_service.files().list(
                q=f"name = '{file_name}'",
                fields="files(id)"
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                raise Exception(f"File {file_name} not found in Drive")
            
            # Delete the first matching file
            file_id = files[0]['id']
            self.drive_service.files().delete(fileId=file_id).execute()
            
            return True
        
        except HttpError as error:
            raise Exception(f"Error deleting file: {error}")

    def get_folder(self, path: str) -> any:
        """
        Get a folder object from Google Drive
        """
        try:
            # Search for the folder
            results = self.drive_service.files().list(
                q=f"name = '{path.strip('/')}' and mimeType = 'application/vnd.google-apps.folder'",
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            
            if not folders:
                raise Exception(f"Folder {path} not found")
            
            return folders[0]
        
        except HttpError as error:
            raise Exception(f"Error getting folder: {error}")

    def get_folder_path(self, folder: any) -> str:
        """
        Get the path of a folder object
        """
        return folder['name']

    def create_folder(self, path: str) -> any:
        """
        Create a folder in Google Drive
        """
        try:
            folder_metadata = {
                'name': path.strip('/'),
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.drive_service.files().create(body=folder_metadata, fields='id, name').execute()
            return folder
        
        except HttpError as error:
            raise Exception(f"Error creating folder: {error}")

    def share_folder(self, folder: any, emails: list[str]) -> any:
        """
        Share a folder with specific emails
        """
        try:
            for email in emails:
                permission = {
                    'type': 'user',
                    'role': 'writer',
                    'emailAddress': email
                }

                # Share the folder
                self.drive_service.permissions().create(
                    fileId=folder['id'],
                    body=permission,
                    fields='id'
                ).execute()
            
            return folder
        
        except HttpError as error:
            raise Exception(f"Error sharing folder: {error}")

    def create_shared_folder(self, path: str, emails: list[str]) -> any:
        """
        Create and share a folder
        """
        try:
            # Create the folder
            folder = self.create_folder(path)
            
            # Share the folder
            return self.share_folder(folder, emails)
        
        except Exception as error:
            raise Exception(f"Error creating and sharing folder: {error}")

    def unshare_folder(self, folder):
        """
        Unshare a folder completely
        """
        try:
            # Get the list of permissions for the file or folder
            permissions = self.drive_service.permissions().list(fileId=folder['id'], fields="permissions(id, type, role)").execute()
            
            permission_list = permissions.get('permissions', [])

            # Delete all permissions except for the owner
            for permission in permission_list:
                # Skip the owner's permission
                if permission['type'] == 'user' and permission['role'] == 'owner':
                    continue
                
                # Delete the permission
                self.drive_service.permissions().delete(fileId=folder['id'], permissionId=permission['id']).execute()

            return True
        
        except HttpError as error:
            raise Exception(f"Error unsharing folder: {error}")

    def unshare_by_email(self, folder: any, emails: list[str]) -> bool:
        """
        Unshare a folder from specific emails
        """
        try:
            # Get the list of permissions for the file or folder
            permissions = self.drive_service.permissions().list(fileId=folder['id'], fields="permissions(id, emailAddress, type, role)").execute()
            
            permission_list = permissions.get('permissions', [])

            for email in emails:
                # Find and delete permission for the specific email
                for permission in permission_list:
                    if permission.get('emailAddress') == email and permission['type'] == 'user':
                        self.drive_service.permissions().delete(fileId=folder['id'], permissionId=permission['id']).execute()
                        break

            return True
        
        except HttpError as error:
            raise Exception(f"Error unsharing by email: {error}")

    def list_shared_files(self, folder=None):
        """
        List shared files
        """
        try:
            # If no specific folder is provided, list all shared files
            query = "sharedWithMe" if folder is None else f"'{folder['id']}' in parents"
            
            results = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name)',
                pageSize=100
            ).execute()

            items = results.get('files', [])
            return [item['name'] for item in items]
        
        except HttpError as error:
            raise Exception(f"Error listing shared files: {error}")

    def list_shared_folders(self):
        """
        List all shared folders
        """
        try:
            query = "mimeType = 'application/vnd.google-apps.folder' and sharedWithMe"
            
            results = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name)',
                pageSize=100
            ).execute()

            items = results.get('files', [])
            return items
        
        except HttpError as error:
            raise Exception(f"Error listing shared folders: {error}")

    def get_members_shared(self, folder: any) -> dict[str] | bool:
        """
        Get members a folder is shared with
        """
        try:
            # Get the list of permissions for the folder
            permissions = self.drive_service.permissions().list(fileId=folder['id'], fields="permissions(id, emailAddress, role)").execute()
            
            permission_list = permissions.get('permissions', [])

            # If no shared permissions exist beyond owner
            if len(permission_list) <= 1:
                return False

            # Collect shared emails
            shared_members = {}
            for permission in permission_list:
                if permission.get('emailAddress') and permission['role'] != 'owner':
                    shared_members[permission['emailAddress']] = permission['role']

            return shared_members if shared_members else False
        
        except HttpError as error:
            raise Exception(f"Error getting shared members: {error}")

    def get_name(self):
        """
        Return the name of the cloud service
        """
        return "G"  #G for Google Drive

    def share(self, folder_path : str, emails : list[str]):
        pass

# Main function to interact with the user
def main():
    print("Google POC")
    email = input("Enter your Google Drive email address: ")
    print(f"Authenticating {email}'s Google Drive account...")
    google = GoogleDrive(email)
    
    if not google.is_authenticated():
        print("Authentication failed.")
        return

    while True:
        print("\nSelect an action:")
        print("1. List files")
        print("2. Upload a file")
        print("3. Download a file")
        print("5. List shared files")
        print("6. Create new folder")
        print("7. Share folder")
        print("8. Delete file")
        print("9. Unshare folder")
        print("10. Exit")

        choice = input("Enter your choice: ")

        if choice == '1':
            files = google.list_files()
            print("Files:", files)
        elif choice == '2':
            file_path = input("Enter the file path to upload: ")
            with open(file_path, 'rb') as f:
                data = f.read()
            dropbox_dest_path = input("Enter the destination path in Google Drive: ")
            google.upload_file(data, os.path.basename(file_path), dropbox_dest_path)
        elif choice == '3':
            dropbox_file_path = input("Enter the file name to download: ")
            downloaded_data = google.download_file(dropbox_file_path, '/')
            with open(dropbox_file_path, 'wb') as f:
                f.write(downloaded_data)
        elif choice == '5':
            shared_files = google.list_shared_files()
            print("Shared files:", shared_files)
        elif choice == '6':
            folder_path = input("Enter folder name to create: ")
            google.create_folder(folder_path)
        elif choice == '7':
            folder_path = input("Enter the folder path to share: ")
            recipient_email = input("Enter email to share with: ")
            folder = google.get_folder(folder_path)
            google.share_folder(folder, [recipient_email])
        elif choice == '8':
            delete_file = input("Enter the file name to delete: ")
            google.delete_file(delete_file, '/')
        elif choice == '9':
            unshare_folder = input("Enter the folder path to unshare: ")
            folder = google.get_folder(unshare_folder)
            google.unshare_folder(folder)
        elif choice == '10':
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    main()