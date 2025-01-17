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


class GoogleDriveImp:
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
                    fields="nextPageToken, files(name)",
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
                    print(f"{index}. {item['name']}")
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
        print("5. Share folder")
        print("6. Unshare folder")
        print("7. List all shared folders and files")
        print("5. Exit")

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
            print("Exiting...")
            break
        else:
            print("Invalid choice, please try again.")

if __name__ == "__main__":
    main()
