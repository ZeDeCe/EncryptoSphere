#TODO: Integrate as a CloudService!

import os
from dotenv import load_dotenv
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.auth.transport.requests import Request

load_dotenv()
# Set up Google Drive API
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
API_KEY = os.getenv("GOOGLE_API_KEY")
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']


class GoogleDrive:
    def __init__(self):
        self.drive_service = None

    # Authenticate with Google Drive
    def authenticate_google_drive(self):
        creds = None
        # Let the user log in and obtain new credentials every time
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
        creds = flow.run_local_server(port=0)
        
        try:
            self.drive_service = build('drive', 'v3', credentials=creds)
            print("Google Drive Authentication successful.")
        
        except HttpError as error:
            print(f"An error occurred: {error}")

    # List files
    def list_files(self):
        try:
            all_files = []
            page_token = None
            
            # Get all files with pagination
            while True:
                results = self.drive_service.files().list(
                    pageSize=100,
                    fields="nextPageToken, files(id, name, mimeType, owners)",
                    pageToken=page_token
                ).execute()
                
                items = results.get('files', [])
                all_files.extend(items)
                page_token = results.get('nextPageToken')
                
                if not page_token:
                    break
            
            if not all_files:
                print("No files found.")
            else:
                print("\nFiles in your Google Drive:")
                print("-" * 50)
                # Print all files
                for index, item in enumerate(all_files, 1):
                    print(f"{index}. {item}")
                print(f"\nTotal files found: {len(all_files)}")
        
        except HttpError as error:
            print(f"Error: {error}")

    # Upload a file
    def upload_file(self, file_path, mime_type='application/octet-stream'):
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                print(f"Error: File not found at path: {file_path}")
                return

            # Check if file is readable
            if not os.access(file_path, os.R_OK):
                print(f"Error: No permission to read file: {file_path}")
                return

            # Get file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                print(f"Error: File is empty: {file_path}")
                return

            # Proceed with upload
            file_metadata = {'name': os.path.basename(file_path)}
            media = MediaFileUpload(file_path, mimetype=mime_type)
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            print(f"File uploaded successfully: {file.get('id')}")
        
        except FileNotFoundError:
            print(f"Error: File not found at path: {file_path}")
        except PermissionError:
            print(f"Error: Permission denied accessing file: {file_path}")
        except HttpError as error:
            print(f"Error during upload: {error}")
        except Exception as error:
            print(f"Unexpected error during upload: {error}")

    # Download a file
    def download_file(self, file_name):
        try:
            # Search file by name
            results = self.drive_service.files().list(
                q=f"name = '{file_name}'",
                fields="files(id, name, mimeType)"
            ).execute()
            
            files = results.get('files', [])
            
            if not files:
                print(f"הקובץ {file_name} לא נמצא ב-Drive")
                return
            
            # Catch the first one (if some files share the same name)
            file_id = files[0]['id']
            mime_type = files[0].get('mimeType', '')
            
            # File path - might change later
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            destination_path = os.path.join(desktop_path, file_name)
            
            # Handle Google Workspace files
            if mime_type.startswith('application/vnd.google-apps'):
                destination_path += '.pdf'
                request = self.drive_service.files().export_media(
                    fileId=file_id,
                    mimeType='application/pdf'
                )
            else:
                request = self.drive_service.files().get_media(fileId=file_id)
            
            with open(destination_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
            
            print(f"Download succesfuly to: {destination_path}")
        
        except HttpError as error:
            print(f"Error: {error}")

    # Create a folder
    def create_folder(self, folder_name):
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        try:
            folder = self.drive_service.files().create(body=folder_metadata, fields='id').execute()
            print(f"Folder '{folder_name}' created with ID: {folder.get('id')}")
        except HttpError as error:
            print(f"An error occurred: {error}")

    def share(self, f_id, email):
        try:
            permission = {
                'type': 'user',       # 'user' to share with specific people; 'anyone' for public sharing
                'role': 'writer',     # 'writer' or 'reader' depending on the permission level
                'emailAddress': email  # Email of the person you want to share with
            }

            # Share the folder by creating a permission for the folder ID
            result = self.drive_service.permissions().create(
                fileId=f_id,     # Folder ID to share
                body=permission,
                fields='id'           # Fields to return in the result (e.g., permission ID)
            ).execute()

            print(f"Folder shared successfully with {email}. Permission ID: {result['id']}")
            return result

        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
    
    def unshare(self, file_id, email):
        try:
            # Get the list of permissions for the file or folder
            permissions = self.drive_service.permissions().list(fileId=file_id, fields="permissions(id, emailAddress, role, type)").execute()
            
            permission_list = permissions.get('permissions', [])

            if not permission_list:
                print(f"No permissions found for file/folder with ID: {file_id}.")
                return

            # Loop through the permissions and delete all except for the owner
            for permission in permission_list:
                # Skip the owner's permission
                if permission['type'] == 'user' and permission['role'] == 'owner':
                    continue
                
                # Delete the permission
                if permission['emailAddress'] == email:
                    self.drive_service.permissions().delete(fileId=file_id, permissionId=permission['id']).execute()
                    print(f"Deleted permission for: {permission.get('emailAddress', permission['type'])} (Role: {permission['role']})")
                    break

            print(f"File or folder with ID: {file_id} has been unshared successfully.")

        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
    def list_shared_files(self):
        try:
            # Query to list all files that are shared
            query = "sharedWithMe"  # 'sharedWithMe' returns files/folders shared with the authenticated user
            
            # Execute the query to get shared files/folders
            results = self.drive_service.files().list(
                q=query,               # Query to list shared files
                spaces='drive',         # Look into the 'drive' space
                fields='nextPageToken, files(id, name, mimeType, owners)',  # Specify the fields to return
                pageSize=100            # Number of files to return in one request (adjust as needed)
            ).execute()

            items = results.get('files', [])

            if not items:
                print('No shared files or folders found.')
                return []

            print('Shared Files and Folders:')
            for item in items:
                # Distinguish between files and folders by MIME type
                file_type = 'Folder' if item['mimeType'] == 'application/vnd.google-apps.folder' else 'File'
                print(f"{file_type}: {item['name']} (ID: {item['id']}) - Owned by: {item['owners'][0]['displayName']}")
            query_shared_by_user = "'me' in owners and trashed = false"
        
            # Execute the query to get files owned by the user
            shared_by_user_results = self.drive_service.files().list(
                q=query_shared_by_user,         # Files owned by the user
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType)',  # Specify fields
                pageSize=100
            ).execute()

            owned_files = shared_by_user_results.get('files', [])

            print("\nFiles and Folders shared by the authenticated user:")
            for item in owned_files:
                file_id = item['id']
                file_name = item['name']
                mime_type = item['mimeType']

                # Check if the file or folder has been shared with others (permissions other than owner)
                permissions = self.drive_service.permissions().list(fileId=file_id, fields="permissions(id, role, type)").execute()
                permission_list = permissions.get('permissions', [])
                
                # Skip files/folders with only owner permissions
                if len(permission_list) > 1:
                    file_type = 'Folder' if mime_type == 'application/vnd.google-apps.folder' else 'File'
                    print(f"{file_type}: {file_name} (ID: {file_id})")

            return items + owned_files

        except HttpError as error:
            print(f"An error occurred: {error}")
            return []



    # Main function to interact with Google Drive
def main():
    print("Google Drive POC")

    drive_service = GoogleDriveImp()
    drive_service.authenticate_google_drive()
    if not drive_service:
        print("Authentication failed.")
        return

    while True:
        print("\nSelect an action:")
        print("1. List files in Google Drive")
        print("2. Upload a file to Google Drive")
        print("3. Download a file from Google Drive")
        print("4. Create a folder in Google Drive")
        print("5. Share file/folder")
        print("6. Unshare folder")
        print("7. List all shared folders and files")
        print("8. Exit")

        choice = input("Enter your choice: ")

        if choice == '1':
            drive_service.list_files()
        elif choice == '2':
            file_path = input("Enter the file path to upload: ")
            drive_service.upload_file(file_path)
        elif choice == '3':
            file_name = input("Enter the file name to download: ")
            drive_service.download_file(file_name)
        elif choice == '4':
            folder_name = input("Enter the folder name to create: ")
            drive_service.create_folder(folder_name)
        elif choice == '5':
            f_name = input("Enter the file/folder ID to share: ")
            email = input("Enter email to share with: ")
            drive_service.share(f_name, email)
        elif choice == '6':
            f_name = input("Enter the file/folder ID to unshare: ")
            email = input("Enter email to unshare with: ")
            drive_service.unshare(f_name, email)
        elif choice == '7':
            drive_service.list_shared_files()
        elif choice == '8':
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    main()
