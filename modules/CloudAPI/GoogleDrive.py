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
        List files in a specific folder on Google Drive.

        :param folder: (Optional) The name or ID of the folder. Defaults to root ('/').
        :return: List of file names within the folder.
        """
        try:
            all_files = []
            page_token = None
            query = ""

            # If folder is specified, get its ID
            if folder != '/':
                folder_id = self.get_folder(folder)  # Get folder ID based on folder name
                if not folder_id:  # If folder not found, raise an error
                    raise Exception(f"Error: Folder '{folder}' not found.")
                query = f"'{folder_id}' in parents"

            # Fetch files from Google Drive
            while True:
                results = self.drive_service.files().list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, mimeType, parents)",
                    pageToken=page_token
                ).execute()

                items = results.get('files', [])
                if items:
                    all_files.extend([item['name'] for item in items])
                page_token = results.get('nextPageToken')

                if not page_token:
                    break

            return all_files

        except Exception as e:
            print(f"Error: {e}") 
            raise

    def upload_file(self, data: bytes, file_name: str, path: str):
        """
        Upload a file to Google Drive
        @param data: The file data to upload
        @param file_name: The name of the file
        @param path: The folder path where the file should be uploaded
        @return: True if the upload was successful, otherwise raises an error
        """
        try:
            if not data:
                raise ValueError("Google Drive: File data is empty")
                
            # Split the folder path into parts
            folder_parts = path.strip('/').split('/')

            if len(folder_parts) < 1:
                raise Exception("Invalid folder path")

            # Start from the root folder
            current_folder_id = 'root'

            # Resolve the folder hierarchy
            for folder in folder_parts:
                results = self.drive_service.files().list(
                    q=f"mimeType = 'application/vnd.google-apps.folder' and name = '{folder}' and '{current_folder_id}' in parents",
                    fields="files(id, name)"
                ).execute()

                folders = results.get('files', [])
                if not folders:
                    # Create folder if it doesn't exist
                    folder_metadata = {
                        'name': folder,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [current_folder_id]
                    }
                    folder = self.drive_service.files().create(body=folder_metadata, fields="id").execute()
                    current_folder_id = folder['id']
                else:
                    current_folder_id = folders[0]['id']

            folder_id = current_folder_id

            # Define file's metadata
            file_metadata = {
                "name": file_name,
                "parents": [folder_id] if folder_id else []
            }

            # Convert to the right format
            media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/octet-stream")

            # Upload
            self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id"
            ).execute()

            return True

        except HttpError as error:
            raise Exception(f"Google Drive: Upload failed - {error}")
        except Exception as error:
            raise Exception(f"Unexpected error during upload: {error}")
    
    def download_file(self, file_name : str, path : str) -> bytes | None:
        """
        Download a file from Google Drive with full path support
        @param file_path: Full path of the file including file name (e.g., '/Folder/Subfolder/filename.txt')
        @param save_path: Optional path for saving (for compatibility, not used in this implementation)
        @return: File content as bytes
        """
        try:
            # Split the folder path into parts
            folder_parts = path.strip('/').split('/')

            if len(folder_parts) < 1:
                raise Exception("Invalid folder path")

            # Start from the root folder
            current_folder_id = 'root'

            # Resolve the folder hierarchy
            for folder in folder_parts:
                results = self.drive_service.files().list(
                    q=f"mimeType = 'application/vnd.google-apps.folder' and name = '{folder}' and '{current_folder_id}' in parents",
                    fields="files(id, name)"
                ).execute()

                folders = results.get('files', [])
                if not folders:
                    raise Exception(f"Folder '{folder}' not found in path")

                current_folder_id = folders[0]['id']

            # Query for the file in the resolved folder
            results = self.drive_service.files().list(
                q=f"name = '{file_name}' and '{current_folder_id}' in parents",
                fields="files(id, name, mimeType)"
            ).execute()

            files = results.get('files', [])
            if not files:
                raise Exception(f"File '{file_name}' not found in path '{path}'")

            file_id = files[0]['id']
            mime_type = files[0].get('mimeType', '')

            # Handle Google Workspace files (e.g., Google Docs, Sheets)
            if mime_type.startswith('application/vnd.google-apps'):
                request = self.drive_service.files().export_media(
                    fileId=file_id,
                    mimeType='application/pdf'
                )
            else:
                request = self.drive_service.files().get_media(fileId=file_id)

            # Execute the download request and return the file content
            return request.execute()

        except Exception as e:
            print(f"Error downloading file: {e}")
            return None
    
    def delete_file(self, file_name: str, path: str):
        """
        Delete a file from Google Drive within a specific path.
        """
        try:
            # If path is a folder ID, we can use it directly.
            # If not, you will need to convert the path to a folder ID first (e.g., using get_folder).
            folder_id = self.get_folder(path) if path != '/' else None

            # Build the query
            query = f"name = '{file_name}'"
            if folder_id:
                query += f" and '{folder_id}' in parents"

            # Perform the query to find the file
            results = self.drive_service.files().list(
                q=query,
                fields="files(id)"
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                raise Exception(f"File '{file_name}' not found in Drive under path '{path}'")
            
            # Get the file ID
            file_id = files[0]['id']
            
            # Perform the delete operation
            self.drive_service.files().delete(fileId=file_id).execute()
            
            return True

        except HttpError as error:
            raise Exception(f"Error deleting file: {error}")

    def get_folder(self, path: str):
        """
        Get the ID of a folder in Google Drive by its full path.
        
        :param path: Full path of the folder (e.g., '/Parent/Child/Folder')
        :return: The ID of the folder if found, otherwise raise an exception
        """
        try:
            path_parts = path.strip('/').split('/')
            
            # params validation
            if len(path_parts) < 1:
                raise Exception("Invalid folder path")
            
            current_folder_id = 'root'
            
            for folder_name in path_parts:
                results = self.drive_service.files().list(
                    q=f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and '{current_folder_id}' in parents",
                    fields="files(id, name)"
                ).execute()
                
                folders = results.get('files', [])
                
                if not folders:
                    raise Exception(f"Folder '{folder_name}' not found in path")
                
                current_folder_id = folders[0]['id']
            
            return current_folder_id

        except Exception as e:
            raise Exception(f"Error while fetching folder ID: {e}")

    def get_folder_path(self, folder: any):
        """
        Get the full path of a folder in Google Drive given its folder object (ID).
        
        :param folder: A folder object (or ID) returned from one of the folder functions.
        :return: The full path of the folder.
        """
        try:
            folder_id = folder if isinstance(folder, str) else folder.get('id')

            if not folder_id:
                raise ValueError("Invalid folder object or missing ID.")

            path = []
            
            while folder_id:
                # Fetch the folder metadata
                folder_metadata = self.drive_service.files().get(
                    fileId=folder_id, 
                    fields="id, name, parents"
                ).execute()

                path.append(folder_metadata["name"])

                # Move to the parent folder
                parent_ids = folder_metadata.get("parents", [])
                folder_id = parent_ids[0] if parent_ids else None

            return "/" + "/".join(reversed(path))

        except Exception as e:
            print(f"Error while fetching folder path: {e}")
            raise

    def create_folder(self, folder_path: str) -> str:
        """
        Create folder on Google Drive and return its full path
        If folder exists, return its existing path
        """
        try:
            path_parts = folder_path.strip('/').split('/')
            
            #validation on parameters
            if len(path_parts) < 1:
                raise Exception("Invalid folder path")
            
            current_folder_id = 'root'
            full_path = ''
            
            for folder_name in path_parts:
                full_path += f'/{folder_name}'
                
                results = self.drive_service.files().list(
                    q=f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and '{current_folder_id}' in parents",
                    spaces="drive",
                    fields="files(id, name)"
                ).execute()
                
                folders = results.get('files', [])
                
                # if not exists, create the folder
                if not folders:
                    folder_metadata = {
                        'name': folder_name,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [current_folder_id]
                    }
                    
                    new_folder = self.drive_service.files().create(
                        body=folder_metadata,
                        fields='id, name'
                    ).execute()
                    
                    current_folder_id = new_folder['id']
                else:
                    current_folder_id = folders[0]['id']
            
            return full_path

        except Exception as e:
            raise Exception(f"Error creating folder: {e}")

    def share_folder(self, folder: any, emails: list[str]):
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

    def create_shared_folder(self, path: str, emails: list[str]):
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
        Unshare a folder completely using the folder ID.
        """
        try:
            # Get the list of permissions for the folder using its ID
            permissions = self.drive_service.permissions().list(fileId=folder, fields="permissions(id, type, role)").execute()
            
            permission_list = permissions.get('permissions', [])

            # Delete all permissions except for the owner
            for permission in permission_list:
                # Skip the owner's permission
                if permission['type'] == 'user' and permission['role'] == 'owner':
                    continue
                
                # Delete the permission
                self.drive_service.permissions().delete(fileId=folder, permissionId=permission['id']).execute()

            return True
        
        except HttpError as error:
            raise Exception(f"Error unsharing folder: {error}")

    def unshare_by_email(self, folder: str, emails: list[str]):
        """
        Unshare a folder from specific emails.
        """
        try:
            # Get the list of permissions for the folder
            permissions = self.drive_service.permissions().list(fileId=folder, fields="permissions(id, emailAddress, type, role)").execute()
            
            permission_list = permissions.get('permissions', [])

            for email in emails:
                # Find and delete permission for the specific email
                for permission in permission_list:
                    if permission.get('emailAddress') == email and permission['type'] == 'user':
                        self.drive_service.permissions().delete(fileId=folder, permissionId=permission['id']).execute()
                        break

            return True
        
        except HttpError as error:
            raise Exception(f"Error unsharing by email: {error}")

    def list_shared_files(self, folder=None):
        pass

    def list_shared_folders(self):
        """
        List all shared folders in all of the cloud
        @return a list of folder objects that represent the shared folders
        """
        try:
            shared_folders = []
            page_token = None

            #my info
            about_info = self.drive_service.about().get(fields="user(emailAddress)").execute()
            my_email = about_info["user"]["emailAddress"]

            query = "mimeType='application/vnd.google-apps.folder' and (sharedWithMe=true or visibility='limited')"

            while True:
                results = self.drive_service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, owners, permissions(emailAddress))",
                    pageToken=page_token
                ).execute()

                items = results.get('files', [])
                if items:
                    for item in items:
                        folder_id = item["id"]
                        folder_name = item["name"]
                        
                        owners = [owner["emailAddress"] for owner in item.get("owners", [])]

                        if my_email in owners:
                            members_shared = [
                                perm["emailAddress"] for perm in item.get("permissions", []) 
                                if perm["emailAddress"] != my_email
                            ]
                        
                        else:
                            members_shared = [email for email in owners if email != my_email]

                        folder_obj = CloudService.Folder(id=folder_id, path=folder_name, shared=True, members_shared=members_shared)
                        shared_folders.append(folder_obj)

                page_token = results.get('nextPageToken')
                if not page_token:
                    break

            return shared_folders

        except Exception as e:
            print(f"Error while fetching shared folders: {e}")
            raise

    def get_members_shared(self, folder: CloudService.Folder):
        """
        Get a list of email addresses the folder is shared with.
        """
        try:
            # Get the list of permissions for the folder
            permissions = self.drive_service.permissions().list(
                fileId=folder.id, 
                fields="permissions(emailAddress, role)"
            ).execute()
            
            permission_list = permissions.get('permissions', [])

            # If no shared permissions exist beyond owner
            if len(permission_list) <= 1:
                return False

            # Collect shared emails
            shared_emails = [
                permission['emailAddress'] for permission in permission_list 
                if permission.get('emailAddress') and permission['role'] != 'owner'
            ]

            return shared_emails if shared_emails else False

        except HttpError as error:
            raise Exception(f"Error getting shared members: {error}")
    
    def get_name(self):
        """
        Return the name of the cloud service
        """
        return "G"  #G for Google Drive


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
        print("1. List all files")
        print("2. Upload a file")
        print("3. Download a file")
        print("5. List shared files")
        print("6. Create new folder")
        print("7. Share folder")
        print("8. Delete file")
        print("9. Unshare folder")
        print("10. Exit")
        print("11. Create shared folder")
        print("12. List all files in specific folder")
        print("13. Unshare folder from specific emails")
        print("14. Get members shared")
        print("15. List shared folders")
        print("16. Test get path")

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
            dropbox_file_path = input("Enter the full path of the file to download (e.g., /Folder/Subfolder/filename): ")
            
            # אם הנתיב לא נמצא, תחזור לברירת מחדל
            if dropbox_file_path == '':
                dropbox_file_path = '/'
            
            downloaded_data = google.download_file(dropbox_file_path, '/')
            
            # אם התוכן שהוחזר לא ריק (bytes), אז נכתוב את הקובץ
            if downloaded_data:
                file_name = dropbox_file_path.split('/')[-1]  # Extract the file name from the path
                with open(file_name, 'wb') as f:
                    f.write(downloaded_data)
                print(f"File '{file_name}' downloaded successfully.")
            else:
                print(f"Failed to download the file from '{dropbox_file_path}'.")
        elif choice == '5':
            shared_files = google.list_shared_files()
            print("Shared files:", shared_files)
        elif choice == '6':
            folder_path = input("Enter full path of folder to create (e.g., Parent/Child/NewFolder): ")
            try:
                created_folder_path = google.create_folder(folder_path)
                print(f"Folder created/found: {created_folder_path}")
            except Exception as e:
                print(f"Error: {e}")
        elif choice == '7':
            folder_path = input("Enter the folder path to share: ")
            recipient_email = input("Enter email to share with: ")

            folder_id = google.get_folder(folder_path)  # Get the ID of the folder
            google.share_folder({'id': folder_id}, [recipient_email])
        elif choice == '8':
            delete_file = input("Enter the file name to delete: ")
            folder_path = input("Enter the folder path to delete from (default is '/'): ") or '/'
            try:
                success = google.delete_file(delete_file, folder_path)
                if success:
                    print(f"File '{delete_file}' deleted successfully.")
                else:
                    print(f"Failed to delete '{delete_file}'.")
            except Exception as e:
                print(f"Error: {e}")
        elif choice == '9':
            unshare_folder_path = input("Enter the folder path to unshare: ")
            try:
                folder_id = google.get_folder(unshare_folder_path)  # Get the ID of the folder
                success = google.unshare_folder(folder_id)  # Unshare folder with its ID
                if success:
                    print(f"Folder '{unshare_folder_path}' has been unshared successfully.")
                else:
                    print(f"Failed to unshare '{unshare_folder_path}'.")
            except Exception as e:
                print(f"Error unsharing folder: {e}")
        elif choice == '10':
            print("Exiting...")
            break
        elif choice == '11':
            folder_path = input("Enter the folder path to create share: ")
            recipient_email = input("Enter email to share with: ")

            folder_id = google.create_folder(folder_path)  # Get folder ID
            print("DEBUG: Created folder ID:", folder_id)
            google.share_folder({'id': folder_id}, [recipient_email])

        elif choice == '12':
            folder = input("Enter the folder to list: ")
            files = google.list_files(folder)
            print("Files:", files)
        
        elif choice == '13':
            unshare_folder_path = input("Enter the folder path to unshare: ")
            emails = input("Enter comma-separated emails to unshare with: ").split(',')
            
            try:
                folder_id = google.get_folder(unshare_folder_path)  # Get the folder ID
                success = google.unshare_by_email(folder_id, emails)  # Unshare with specific emails
                if success:
                    print(f"Folder '{unshare_folder_path}' has been unshared from the specified emails.")
                else:
                    print(f"Failed to unshare '{unshare_folder_path}' from the specified emails.")
            except Exception as e:
                print(f"Error unsharing folder from emails: {e}")

        elif choice == '14':
            unshare_folder_path = input("Enter the folder path to check members shared: ")
            try:
                folder_id = google.get_folder(unshare_folder_path)  # Get the folder ID
                shared_members = google.get_members_shared(folder_id)  # Get shared members using folder ID
                
                if shared_members == False:
                    print("Not shared")
                elif shared_members:
                    print(f"Shared members of folder '{unshare_folder_path}':")
                    for email in shared_members:
                        print(email)
                else:
                    print(f"No members shared the folder '{unshare_folder_path}'.")
            except Exception as e:
                print(f"Error getting shared members: {e}")
        
        elif choice == '15':
            print("Fetching shared folders...")
            try:
                shared_folders = google.list_shared_folders()
                
                if not shared_folders:
                    print("No shared folders found.")
                else:
                    print("Shared folders:")
                    for folder in shared_folders:
                        print(f"Folder Name: {folder.path}, ID: {folder.id}, Shared: {folder.shared}, Members: {', '.join(folder.members_shared) if folder.members_shared else 'No members'}")
            
            except Exception as e:
                print(f"Error fetching shared folders: {e}")
        
        elif choice == '16':
            folder_path = input("Enter the folder name to get its path: ")
            try:
                folder = google.get_folder(folder_path)  # מקבל את אובייקט התיקייה (ID)
                folder_full_path = google.get_folder_path({'id': folder})  # קורא לפונקציה החדשה
                print(f"Full path of '{folder_path}': {folder_full_path}")
            except Exception as e:
                print(f"Error getting folder path: {e}")
        
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    main()
