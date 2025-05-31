import os
import io
import json
from dotenv import load_dotenv
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload, HttpRequest
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from modules.CloudAPI.CloudService import CloudService
from google_auth_httplib2 import AuthorizedHttp
from modules.CloudDataManager import CloudDataManager
from typing import Iterable
import httplib2

load_dotenv()
# Set up Google Drive API
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
API_KEY = os.getenv("GOOGLE_API_KEY")
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']
GOOGLE_TOKEN_PATH = "cloud_tokens.json"
GOOGLE_ENCRYPTOSPHERE_ROOT = "EncryptoSphere"

class GoogleDrive(CloudService):
    
    def authenticate_cloud(self):
        """
        Authenticate with Google Drive using CloudDataManager.
        Loads the token from JSON by email, or initiates new login if needed.
        Also creates the root folder if it does not exist.
        """
        if self.authenticated:
            return True

        self.token_manager = CloudDataManager("EncryptoSphereApp", "google")
        creds = None

        try:
            print("Google Drive     : Loading clouds token file...")
            token_data = self.token_manager.get_data(self.email)
            if token_data:
                creds = Credentials(
                    token=token_data.get('token'),
                    refresh_token=token_data.get('refresh_token'),
                    token_uri=token_data.get('token_uri'),
                    client_id=token_data.get('client_id'),
                    client_secret=token_data.get('client_secret'),
                    scopes=token_data.get('scopes')
                )

            # Refresh or start new authentication
            if creds and not creds.expired:
                pass
            elif creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._save_google_token_to_json(creds)
            else:
                # Start new authentication flow
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
                creds = flow.run_local_server(port=0)

                # Verify email
                if not self._verify_google_token_for_user(creds):
                    return False

                self._save_google_token_to_json(creds)

            # Set up Drive service
            def build_request(http, *args, **kwargs):
                new_http = AuthorizedHttp(creds, http=httplib2.Http())
                return HttpRequest(new_http, *args, **kwargs)

            authorized_http = AuthorizedHttp(creds, http=httplib2.Http())
            self.drive_service = build('drive', 'v3', requestBuilder=build_request, http=authorized_http)

            self.authenticated = True
            print("Google Drive     : Authentication successful")

        except Exception as e:
            print(f"Google Drive     : Authentication error: {e}")
            return False

        try:
            self.root_folder = self.create_folder(GOOGLE_ENCRYPTOSPHERE_ROOT, CloudService.Folder("", ""))
            self.root_folder.name = ""
            print("Google Drive     : Root folder ready")
        except Exception as e:
            print(f"Google Drive     : Failed to create root folder: {e}")
            return False

        return True

    
    def _save_google_token_to_json(self, creds):
        try:
            token_data = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            }
            self.token_manager.add_data({self.email: token_data})
            print("Google Drive     : Token saved successfully.")
        except Exception as e:
            print(f"Google Drive     : Error saving token: {e}")

    
    def _verify_google_token_for_user(self, creds):
        """
        Verify that the credentials match the expected user email.
        """
        try:
            drive_service = build('drive', 'v3', credentials=creds)
            user_info = drive_service.about().get(fields="user").execute()
            current_email = user_info['user']['emailAddress']
            if current_email == self.email:
                return True
            else:
                print("Google Drive     : Email mismatch during authentication.")
                return False
        except Exception as e:
            print(f"Google Drive     : Error verifying email: {e}")
            return False



    def get_children(self, folder: CloudService.Folder, filter=None):
        """
        Get all file and folder objects that are children of the specified folder in Google Drive
        @param folder: the folder object to get the children of
        """
        try:
            query = f"'{folder._id}' in parents and trashed=false"
            page_token = None
            while True:
                response = self.drive_service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType)',
                    pageToken=page_token
                ).execute()
                
                for file in response.get('files', []):
                    if filter is not None and file['name'].startswith(filter):
                        continue

                    if file['mimeType'] == 'application/vnd.google-apps.folder':
                        yield CloudService.Folder(id=file['id'], name=file['name'])
                    else:
                        yield CloudService.File(id=file['id'], name=file['name'])
                
                page_token = response.get('nextPageToken', None)
                if page_token is None:
                    break

        except Exception as e:
            raise Exception(f"Error {e}")


    def list_files(self, folder: CloudService.Folder, filter=""):
        """
        List files in a specific folder on Google Drive.

        :param folder: CloudService.Folder object
        :param filter: (Optional) Filter string to match file names starting with it.
        :return: Yields CloudService.File objects.
        """
        try:
            page_token = None
            query = f"'{folder._id}' in parents and mimeType != 'application/vnd.google-apps.folder' and trashed = false"

            while True:
                results = self.drive_service.files().list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, mimeType)",
                    pageToken=page_token
                ).execute()

                items = results.get('files', [])
                for item in items:
                    if item['name'].startswith(filter):
                        yield CloudService.File(id=item['id'], name=item['name'])

                page_token = results.get('nextPageToken')
                if not page_token:
                    break

        except Exception as e:
            print(f"Google Drive: API error: {e}")
            raise


    def get_items_by_name(self, filter: str, folders: list[CloudService.Folder]) -> Iterable[CloudService.CloudObject]:
        """
        Get all files and folders in the given folders where the name contains the filter string.
        Performs a recursive search.
        """
        try:
            for folder in folders:
                folder_id = folder._id
                query = f"'{folder_id}' in parents and trashed = false"
                page_token = None

                while True:
                    results = self.drive_service.files().list(
                        q=query,
                        pageSize=100,
                        fields="nextPageToken, files(id, name, mimeType)",
                        pageToken=page_token
                    ).execute()

                    items = results.get('files', [])
                    for item in items:
                        if filter.lower() in item['name'].lower():
                            is_folder = item['mimeType'] == 'application/vnd.google-apps.folder'
                            if is_folder:
                                # Yield the folder and recursively search its children
                                subfolder = CloudService.Folder(id=item['id'], name=item['name'])
                                yield subfolder
                                yield from self.get_items_by_name(filter, [subfolder])
                            else:
                                yield CloudService.File(id=item['id'], name=item['name'])

                    page_token = results.get('nextPageToken')
                    if not page_token:
                        break

        except Exception as e:
            print(f"Google Drive - Error in get_items_by_name: {e}")
            raise

    def upload_file(self, data: bytes, file_name: str, parent: CloudService.Folder):
        """
        Upload a file to Google Drive, updating it if a file with the same name already exists
        :param data: The file data to upload
        :param file_name: The name of the file
        :param parent: CloudService.Folder object where the file should be uploaded
        :return: CloudService.File object representing the uploaded file
        """
        try:
            if not data:
                raise ValueError("Google Drive: File data is empty")

            folder_id = parent._id

            # Check if file already exists in the folder
            results = self.drive_service.files().list(
                q=f"name='{file_name}' and '{folder_id}' in parents and trashed=false",
                fields="files(id, name)",
                pageSize=1
            ).execute()

            existing_files = results.get('files', [])

            media = MediaIoBaseUpload(io.BytesIO(data), mimetype="application/octet-stream")

            if existing_files:
                # Update the existing file
                file_id = existing_files[0]['id']
                updated_file = self.drive_service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
                print(f"Google Drive: {file_name} updated successfully.")
                return CloudService.File(id=updated_file['id'], name=file_name)
            else:
                # Upload new file
                file_metadata = {
                    "name": file_name,
                    "parents": [folder_id]
                }
                created_file = self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, name"
                ).execute()
                print(f"Google Drive: {file_name} uploaded successfully.")
                return CloudService.File(id=created_file['id'], name=file_name)

        except HttpError as error:
            raise Exception(f"Google Drive: Upload failed - {error}")
        except Exception as error:
            raise Exception(f"Google Drive: Unexpected error during upload: {error}")

    
    def download_file(self, file: CloudService.File) -> bytes | None:
        """
        Download a file from Google Drive and return the file's data.
        """
        try:
            # First, get the file metadata
            file_metadata = self.drive_service.files().get(fileId=file._id, fields="id, name, mimeType").execute()
            mime_type = file_metadata.get('mimeType', '')

            # Handle Google Workspace files (Docs, Sheets) by exporting
            if mime_type.startswith('application/vnd.google-apps'):
                request = self.drive_service.files().export_media(
                    fileId=file._id,
                    mimeType='application/pdf'
                )
            else:
                request = self.drive_service.files().get_media(fileId=file._id)

            # Download the file content
            file_data = request.execute()
            print(f"Google Drive: file {file.name} downloaded successfully.")
            return file_data

        except HttpError as e:
            print(f"Google Drive- HTTP error failed to download file {file.name}: {e}")
            return None
        except FileNotFoundError:
            print(f"Google Drive: Failed to download file, the file {file.name} was not found.")
            return None
        except Exception as e:
            raise Exception(f"Google Drive-Error: {e}")

    
    def delete_file(self, file: CloudService.File):
        """
        Delete file from Google Drive by file object
        """
        try:
            file_id = file._id

            self.drive_service.files().delete(fileId=file_id).execute()
            print(f"Google Drive: {file.name} deleted successfully.")
            return True
        except HttpError as error:
            raise Exception(f"Google Drive- Error deleting file: {error}")
        except Exception as e:
            print(f"Google Drive- Unexpected error: {e}")
            return False
        
    
    def delete_folder(self, folder: CloudService.Folder):
        """
        Delete folder from Google Drive by folder object.
        """
        try:
            folder_id = folder._id

            # delete folder just like file
            self.drive_service.files().delete(fileId=folder_id).execute()
            print(f"Google Drive: Folder '{folder.name}' deleted successfully.")
            return True
        except HttpError as error:
            raise Exception(f"Google Drive - Error deleting folder: {error}")
        except Exception as e:
            print(f"Google Drive - Unexpected error deleting folder: {e}")
            return False


    def get_session_folder(self, name: str) -> CloudService.Folder:
        """
        Get the session folder from Google Drive, create it if it doesn't exist.
        """
        try:
            query = (
                f"'{self.root_folder._id}' in parents and "
                f"mimeType = 'application/vnd.google-apps.folder' and "
                f"name = '{name}' and trashed = false"
            )

            results = self.drive_service.files().list(
                q=query,
                spaces='drive',
                fields="files(id, name)",
                pageSize=1
            ).execute()

            files = results.get('files', [])
            if files:
                return CloudService.Folder(id=files[0]['id'], name=files[0]['name'], shared=False)

            new_folder = self.create_folder(name, self.root_folder)
            new_folder.name = "/"
            return new_folder

        except HttpError as error:
            raise Exception(f"Google Drive - Error getting/creating session folder: {error}")
        except Exception as e:
            raise Exception(f"Google Drive - Unexpected error in get_session_folder: {e}")

    
        
    def create_folder(self, name: str, parent: CloudService.Folder) -> CloudService.Folder:
        """
        Create a folder in Google Drive under the given parent folder.
        Returns the created or existing folder as a CloudService.Folder object.
        """
        try:
            parent_id = parent._id or "root" 

            # Check if folder already exists under the parent
            query = (
                f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
                f"and '{parent_id}' in parents and trashed = false"
            )

            results = self.drive_service.files().list(
                q=query,
                spaces="drive",
                fields="files(id, name)",
            ).execute()

            folders = results.get('files', [])

            if folders:
                existing = folders[0]
                return CloudService.Folder(id=existing['id'], name=existing['name'], shared=False)

            # Folder doesn't exist, so we create it
            folder_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }

            new_folder = self.drive_service.files().create(
                body=folder_metadata,
                fields='id, name'
            ).execute()

            return CloudService.Folder(id=new_folder['id'], name=new_folder['name'], shared=False)

        except Exception as e:
            raise Exception(f"Google Drive - Error creating folder '{name}' under parent '{parent.name}': {e}")

    
    def create_shared_session(self, name, emails):
        try:
            folder = self.create_folder(name, self.root_folder)  # folder is CloudService.Folder object
            return self.share_folder(folder, emails)
        except HttpError as e:
            print(f"Google Drive     : API Error occurred: {e}")
        except Exception as e:
            print(f"Google Drive     : Error occurred: {e}")
        return None

    
    def share_folder(self, folder: CloudService.Folder, emails: list[str]) -> CloudService.Folder:
        """
        Share a folder on Google Drive.
        """
        try:
            shared_members = self.get_members_shared(folder)
            
            if not isinstance(shared_members, list):
                shared_members = []

            to_add = [email for email in emails if email not in shared_members]

            for email in to_add:
                if not self._add_member_to_share_folder(folder._id, email):
                    print(f"Failed to share folder with {email}")
                    return None
                print(f"Folder shared successfully with {email}!")

            return CloudService.Folder(id=folder._id, name=folder.name, shared=True)

        except HttpError as e:
            raise Exception(f"Google Drive: Error: {e}")


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
        
        
    def _add_member_to_share_folder(self, folder_id, email):
        """
        Protected function to share a folder with a user via email
        """
        try:
            permission = {
                'type': 'user',
                'role': 'writer',  # or 'reader' for read-only
                'emailAddress': email
            }
            self.drive_service.permissions().create(
                fileId=folder_id,
                body=permission,
                fields='id',
                sendNotificationEmail=False
            ).execute()
            return True
        except HttpError as e:
            print(f"Error sharing folder '{folder_id}' with {email}: {e}")
            return None


    def unshare_folder(self, folder: CloudService.Folder):
        """
        Unshare a folder on Google Drive by removing all user permissions
        """
        if not folder.is_shared():
            raise Exception("Error: Folder is not shared")
        
        try:
            permissions = self.drive_service.permissions().list(fileId=folder._id).execute()
            for permission in permissions.get('permissions', []):
                if permission['role'] != 'owner':
                    self.drive_service.permissions().delete(
                        fileId=folder.shared,
                        permissionId=permission['id']
                    ).execute()
            print(f"Folder '{folder.name}' has been unshared.")
            return True
        except HttpError as e:
            raise Exception(f"Error unsharing folder: {e}")

    def get_owner(self, folder: CloudService.Folder):
        """
        Get the owner of the shared folder
        If folder is not shared, raise an error
        """
        if not folder.shared:
            raise Exception("Error: Folder is not shared")
        if hasattr(folder, "_owner"): # cache it because owner doesn't change
            return folder._owner
        try:
            permissions = self.drive_service.permissions().list(
                fileId=folder._id,
                fields="permissions(emailAddress, role, type)"
            ).execute()

            permission_list = permissions.get('permissions', [])
            for permission in permission_list:
                if permission['role'] == 'owner':
                    folder._owner = permission['emailAddress']
                    return permission['emailAddress']

            return None

        except HttpError as error:
            raise Exception(f"Error getting owner: {error}")
    
    def leave_shared_folder(self, folder):
        """
        Leave a shared folder
        Exit the shared folder without deleting it
        """
        if not folder.shared:
            raise Exception("Error: Folder is not shared")

        try:

            # List permissions for the folder
            permissions = self.drive_service.permissions().list(
                fileId=folder._id,
                fields="permissions(id, emailAddress, role, type)"
            ).execute()

            permission_list = permissions.get('permissions', [])
            my_permission_id = None

            for permission in permission_list:
                if permission.get('emailAddress') == self.get_email() and permission['type'] == 'user':
                    my_permission_id = permission['id']
                    break

            if not my_permission_id:
                raise Exception("Error: Trying to leave folder as owner.") # Call delete_folder or unshare_folder instead

            self.drive_service.permissions().delete(
                fileId=folder._id,
                permissionId=my_permission_id
            ).execute()
            print(f"Left shared folder '{folder.name}'.")
            return True
        except HttpError as error:
            raise Exception(f"Error leaving shared folder: {error}")

    def unshare_by_email(self, folder: CloudService.Folder, emails: list[str]):
        """
        Unshare a folder from specific emails in Google Drive.
        """
        if not folder.shared:
            raise Exception("Error: Folder must be shared to unshare users.")

        try:
            permissions = self.drive_service.permissions().list(
                fileId=folder._id,
                fields="permissions(id, emailAddress, type, role)"
            ).execute()

            permission_list = permissions.get('permissions', [])

            for email in emails:
                for permission in permission_list:
                    if permission.get('emailAddress') == email and permission['type'] == 'user':
                        self.drive_service.permissions().delete(
                            fileId=folder._id,
                            permissionId=permission['id']
                        ).execute()
                        print(f"Removed {email} from folder '{folder.name}'.")

            return True

        except HttpError as error:
            raise Exception(f"Error unsharing by email: {error}")


    def list_shared_folders(self, filter=""):
        """
        List all shared folders that are either shared with me or that I've shared with others.
        @param filter - Optional suffix to match folder names (like Dropbox).
        @return a list of folder objects that represent the shared folders.
        """
        try:
            shared_folders = []
            page_token = None
            
            # Get the authenticated user's email
            about_info = self.drive_service.about().get(fields="user(emailAddress)").execute()
            my_email = about_info["user"]["emailAddress"]
            
            # Query to find all shared folders - both shared with me and ones I shared
            query = "mimeType='application/vnd.google-apps.folder' and (sharedWithMe=true or visibility='limited')"
            
            while True:
                results = self.drive_service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, owners, permissions(emailAddress), parents)",
                    pageToken=page_token
                ).execute()
                
                items = results.get('files', [])
                if items:
                    for item in items:
                        folder_id = item["id"]
                        folder_name = item["name"]

                        # Check filter match (like Dropbox)
                        if filter and not folder_name.endswith(filter):
                            continue
                        
                        # Check if the folder is actually shared (has members other than myself)
                        permissions = item.get("permissions", [])
                        shared_with_others = False
                        members_shared = []
                        
                        for perm in permissions:
                            if "emailAddress" in perm and perm["emailAddress"] != my_email:
                                shared_with_others = True
                                members_shared.append(perm["emailAddress"])
                        
                        if shared_with_others:
                            # Get owners
                            owners = [owner.get("emailAddress") for owner in item.get("owners", [])]
                            for owner_email in owners:
                                if owner_email and owner_email not in members_shared:
                                    members_shared.append(owner_email)
                            
                            full_path = "/" + folder_name

                            folder_obj = CloudService.Folder(
                                id=folder_id,
                                name=folder_name,
                                shared=True
                            )
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
        Returns False if the folder is not shared or has no members.
        """
        if not folder.shared:
            return False

        try:
            permissions = self.drive_service.permissions().list(
                fileId=folder._id,
                fields="permissions(emailAddress, role, type)"
            ).execute()

            permission_list = permissions.get('permissions', [])
            shared_emails = [
                p['emailAddress'] for p in permission_list
                if p.get('emailAddress') and p['type'] == 'user'
            ]

            return shared_emails if shared_emails else False

        except HttpError as error:
            raise Exception(f"Error getting shared members: {error}")
         
    
    def get_name(self):
        """
        Return the name of the cloud service
        """
        return "G"  #G for Google Drive

    def enrich_item_metadata(self, item: CloudService.File | CloudService.Folder) -> dict:
        """
        Enrich a CloudService.File or CloudService.Folder object by retrieving its full metadata, including the path.
        @param item: The File or Folder object to enrich.
        @return: A dictionary containing the enriched metadata, including the full path.
        """
        try:
            # Use Google Drive API to get metadata
            metadata = self.drive_service.files().get(fileId=item._id, fields="id, name, mimeType, parents, size, modifiedTime").execute()

            # Determine if the item is a file or folder
            if isinstance(item, CloudService.File) and metadata["mimeType"] != "application/vnd.google-apps.folder":
                return {
                    "id": metadata["id"],
                    "name": metadata["name"],
                    "path": self._get_full_path(metadata["id"]),
                    "type": "file",
                    "size": metadata.get("size"),
                    "modified": metadata.get("modifiedTime"),
                }
            elif isinstance(item, CloudService.Folder) and metadata["mimeType"] == "application/vnd.google-apps.folder":
                return {
                    "id": metadata["id"],
                    "name": metadata["name"],
                    "path": self._get_full_path(metadata["id"]),
                    "type": "folder",
                }
            else:
                raise ValueError(f"Unexpected metadata type for item: {item}")

        except HttpError as e:
            print(f"Error retrieving metadata for item '{item.name}': {e}")
            raise

    def _get_full_path(self, file_id: str) -> str:
        """
        Helper function to recursively build the full path of a file or folder in Google Drive.
        @param file_id: The ID of the file or folder.
        @return: The full path as a string.
        """
        path = []
        while file_id:
            metadata = self.drive_service.files().get(fileId=file_id, fields="id, name, parents").execute()
            path.append(metadata["name"])
            file_id = metadata.get("parents", [None])[0]  # Get the parent ID or None if it's the root
        return "/" + "/".join(reversed(path))