"""
This is the main file that runs the the entire program
Runs the GUI and handles the requests from the GUI to the backend
"""
import os
from dotenv import load_dotenv
load_dotenv()
from CloudManager import CloudManager
from SharedCloudManager import SharedCloudManager
from modules.Encrypt import *
from modules.Split import *
from modules.CloudAPI import *
from SessionManager import SessionManager
import customtkinter as ctk
from threading import Thread
import concurrent.futures
import time
import threading
from functools import wraps
from LoginManager import LoginManager
import hashlib
import json
import shutil

import utils.DialogBox as DialogBox
import app as app


# This is temporary:
from cryptography.fernet import Fernet

FILE_INDEX_SEPERATOR = "#"
SYNC_TIME = 90 # 1 min 30 sec
MAIN_SESSION  = "main_session"

class Gateway:
    """
    This class creates EncryptoSphere process and handles UI requests.
    Acts as the api between the UI and the "backend" of the program. 
    """

    def __init__(self):
        self.manager = None
        self.session_manager = None
        self.executor = concurrent.futures.ThreadPoolExecutor()
        self.active_fd_sync = False
        self.active_sessions_sync = False
        self.active_shared_folder_sync = False
        self.sync_future_callbacks = []
        self.authenticated_clouds = []
        self.email = None
        self.metadata_exists = False
        self.login_manager = LoginManager()
        
        self.search_results = []  # Store the most recent search results
        self.search_results_cloud = None  # Store the cloud of the most recent search resultsN

    def promise(func):
        """
        Decorator to run a function in a separate thread and return a Future object
        Also attaches a callback to the function if given
        """
        @wraps(func)
        def wrapper(self, callback, *args, **kwargs):
            future : concurrent.futures.Future = self.executor.submit(func, self, *args, **kwargs)
            if not callback is None:
                future.add_done_callback(callback)
                def exception_caller(f):
                    if f.exception():
                        print(f"Error occurred in a promise: {f.exception()}")
                future.add_done_callback(exception_caller)
            return future
        return wrapper
    
    def enrichable(func):
        """
        Decorator for Gateway methods that take file_path or folder_path.
        If the argument is an int, it will get the actual path.
        """

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Find the argument name (file_path or folder_path)
            import inspect
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            params.remove('self')  # Remove 'self' from the parameters list

            # Find which param is file_path or folder_path
            for i, name in enumerate(params):
                if name == "path" and len(args) > i:
                    arg = args[i]
                    if isinstance(arg, int):
                        # Enrich and replace in args
                        path = self.get_path_from_searchindex(arg)
                        # Replace the int with the enriched value
                        args = list(args)
                        args[i] = path
            return func(self, *args, **kwargs)
        return wrapper

    def is_metadata_exists(self, cloud : CloudService):
        return CloudManager.is_metadata_exists(cloud, MAIN_SESSION, "$LOGIN_META")

    def get_default_encryption_algorithm(self):
        """
        Returns the default encryption algorithm
        """
        return self.manager.encrypt.get_name()
    def get_default_split_algorithm(self):
        """
        Returns the default split algorithm
        """
        return self.manager.split.get_name()

    def get_metadata_exists(self):
        return self.metadata_exists
    
    def get_algorithms(self):
        """
        Returns the list of algorithms
        """
        return Encrypt.get_classes(), Split.get_classes()
    
    def get_current_session(self):
        """
        Returns the current session
        """
        return "0" if self.current_session == self.manager else self.current_session.get_uid()
    
    @promise
    def cloud_authenticate(self, cloud_name: str):
        """
        Authenticates a single cloud service using its short identifier (e.g., 'G' for GoogleDrive).
        The cloud_name is matched using each class's get_name() method.
        """
        supported_clouds = CloudService.get_cloud_classes()

        for cloud_class in supported_clouds:
            if cloud_class.get_name_static().lower() == cloud_name.lower():
                cloud = cloud_class(self.email)
                if not cloud.authenticate_cloud():
                    raise Exception(f"Authentication failed for {cloud.get_name()}")
                self.authenticated_clouds.append(cloud)
                if not self.metadata_exists:
                    self.metadata_exists = self.is_metadata_exists(cloud)    
                return cloud

        raise ValueError(f"Unsupported cloud service: {cloud.get_name()}")
    
    @promise
    def clouds_authenticate_by_token(self):
        """
        Authenticates all supported cloud services using a token.
        Returns a list of cloud objects that were successfully authenticated.
        """
        supported_clouds = CloudService.get_cloud_classes()
        autenticated_clouds = []
        futures = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for cloud_class in supported_clouds:
                cloud = cloud_class(self.email)
                futures[executor.submit(cloud.authenticate_by_token)] = cloud
            for future in concurrent.futures.as_completed(futures):
                try:
                    if future.result():
                        cloud = futures[future]
                        autenticated_clouds.append(cloud)
                        if not self.metadata_exists and self.is_metadata_exists(cloud):
                            self.metadata_exists = True
                except Exception as e:
                    print(f"Failed to authenticate {futures[future].get_name()}: {e}")
        self.authenticated_clouds = autenticated_clouds
        return autenticated_clouds


    def set_email(self, email: str):
        self.email = email


    def get_authenticated_clouds(self):
        """
        Returns the list of authenticated clouds
        """
        return self.authenticated_clouds
    
    
    @promise
    def app_authenticate(self, password: str):
        """
        Authenticates the app using login metadata ($LOGIN_META), 
        then loads main metadata ($META) to initialize session.
        """
        if not self.authenticated_clouds:
            return "No authenticated clouds"

        try:
            self.login_manager.load_login_metadata(password, self.authenticated_clouds[0], MAIN_SESSION)
        except Exception as e:
            return "Failed to load login metadata"

        try:
            key = self.login_manager.login(
                input_password=password,
                salt=self.login_manager.salt,
                auth_encrypted_hex=self.login_manager.encrypted_auth.hex(),
                auth_hash=self.login_manager.auth_hash,
                encryption_type=self.login_manager.encryption_type
            )
        except Exception as e:
            return "Failed to authenticate: Password is incorrect or metadata is corrupted"
        
        metadata = self.login_manager.login_metadata
        if not metadata:
            return "Login metadata is empty or not found"
        try:
            encryption_type = metadata.get("encrypt")
            split_type = metadata.get("split")

            encryptor_class = Encrypt.get_class(encryption_type)
            encryptor = encryptor_class()
            encryptor.set_key(encryptor.generate_key_from_key(key))

            self.manager = CloudManager(
                self.authenticated_clouds,
                MAIN_SESSION,
                Split.get_class(split_type)(),
                encryptor
            )
            self.session_manager = SessionManager(self.manager)
            status = self.manager.authenticate()
            if not status:
                return "Failed to authenticate with cloud services"
            self.current_session = self.manager
            self.start_sync_new_sessions_task()
            return True
        except Exception as e:
            return "Unknown error during authentication"


    @promise
    def create_account(self, password: str, encrypt_alg: str, split_alg: str) -> bool:
        """
        Creates a new account: both login metadata ($LOGIN_META) and main metadata ($META).
        """
        if not password or len(password) < 6:
            raise ValueError("Password is too short")

        if not self.authenticated_clouds:
            raise ValueError("No cloud services provided")

        self.login_manager.cloud = self.authenticated_clouds[0]
        self.login_manager.root = MAIN_SESSION

        # check if metadata alredy exists
        try:
            if CloudManager.is_metadata_exists(self.authenticated_clouds[0], MAIN_SESSION, "$LOGIN_META"):
                raise Exception("Account already exists – metadata found in cloud")
        except Exception:
            raise RuntimeError("Could not access cloud to check for existing account")

        # create $LOGIN_META
        try:
            self.login_manager.create_login_metadata(password, encrypt_alg, split_alg)
            CloudManager.upload_metadata(
                self.authenticated_clouds,
                MAIN_SESSION,
                self.login_manager.login_metadata,
                "$LOGIN_META"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create or upload login metadata: {e}")

        # create $META
        try:
            split = Split.get_class(split_alg)()
            key = self.login_manager.create_key_from_password(password, self.login_manager.salt)
            encryptor_class = Encrypt.get_class(encrypt_alg)
            encryptor = encryptor_class()
            encryptor.set_key(encryptor.generate_key_from_key(key))

            self.manager = CloudManager(
                self.authenticated_clouds,
                MAIN_SESSION,
                split,
                encryptor
            )
            self.manager.authenticate()
            self.current_session = self.manager
            self.session_manager = SessionManager(self.manager)
            self.start_sync_new_sessions_task()

        except Exception as e:
            raise RuntimeError(f"Failed to create or upload main metadata: {e}")

        return True


    def get_clouds(self):
        return CloudService.get_cloud_classes()
        

    def change_session(self, uid=None):
        """
        Change the current session to the one specified by path
        @param path: the path to the session to change to
        """
        try:
            if uid:
                self.current_session = self.session_manager.get_session(uid)
            else:
                self.current_session = self.session_manager.main_session
        except Exception as e:
            print(f"Error in change_session: {e}")

    @promise
    @enrichable
    def get_items_in_folder_async(self, path="/"):
        try:
            return self.current_session.get_items_in_folder(path)
        except Exception as e:
            print(f"Error in get_items_in_folder_async: {e}")
            return []

    @promise
    def get_search_results_sharedsessions(self, search_string):
        """
        Search for items matching the given string in shared sessions.
        @param search_string: The filter string to search for.
        @param path: The folder path to start the search from.
        @return: A list of dictionaries with item details.
        """
        try:
            for folder in self.get_shared_folders():
                if folder["uid"].startswith(search_string):
                    yield folder
        except Exception as e:
            print(f"Error in get_search_results_sharedsessions: {e}")

    @promise
    def get_search_results_async(self, search_string, path):
        """
        Search for items matching the given string asynchronously.
        @param search_string: The filter string to search for.
        @param path: The folder path to start the search from.
        @return: A generator yielding dictionaries with item details.
        """
        try:
            print(f"Searching for items matching: {search_string}")
            item_iter = self.current_session.search_items_by_name(search_string, path)
            self.search_results = []
            for index, item in enumerate(item_iter):
                self.search_results.append(item)
                if isinstance(item, CloudService.File):
                    split = item.name.split(FILE_INDEX_SEPERATOR)  # Maybe just take care of this in CloudManager?
                yield {
                    "name": split[1] if isinstance(item, CloudService.File) else item.name,
                    "id": index,
                    "type": "file" if isinstance(item, CloudService.File) else "folder",
                    "path": None,
                    "uid": "0" if self.current_session == self.manager else self.current_session.get_uid(),
                    "search_index": index,
                }
        except Exception as e:
            print(f"Error in get_search_results_async: {e}")

    @promise
    def sync_session(self):
        try:
            print("Refresh button clicked")
            ret = self.session_manager.sync_new_sessions()
            print(f"Finished refreshing")
            return ret
        except Exception as e:
            print(f"Error in sync_session: {e}")
            return False

    @promise
    def refresh_shared_folder(self):
        # We don't actually need to do anything, just call get_items_in_folder for that shared folder
        pass

    @promise
    @enrichable
    def open_file(self, path):
        """
        Open file function
        @param file_id: the id of the file to open
        @return: True if the file was opened successfully, False otherwise
        """

        print(f"Open file selected: {path}")
        return self.current_session.open_file(path)


    @promise
    @enrichable
    def download_file(self, path):
        """
        Download file function
        @param file_id: the id of the file to download
        @return: True if the file was downloaded successfully, False otherwise
        """

        print(f"Download file selected: {path}")
        return self.current_session.download_file(path)

    
    @promise
    @enrichable
    def copy_file(self, path: str, destination_path: str, source_session: str):
        """
        Copy and paste files to a destination path.
        Delegates the logic to the CloudManager.
        @param files: List of file paths to copy.
        @param destination_path: The destination folder path.
        @param source_session: The session UID from which the files are copied, 0 if main session
        @return: List of new file paths in the destination folder.
        """
        try:
            print(f"Copying file: session: {source_session}, current: {self.current_session}, path: {path}, destination: {destination_path}")
            if self.get_current_session() == source_session:
                print(f"Copying file (same session): {path} to destination: {destination_path}")
                return self.current_session.copy_file(path, destination_path)
            else:
                # If the source session is different, we need to handle it accordingly
                print(f"Copying file from different session: {source_session} to {self.get_current_session()}")
                
                source_sess = self.session_manager.get_session(source_session)
                if source_sess is None:
                    source_sess = self.session_manager.main_session

                existing_files = {item["name"] for item in self.current_session.get_items_in_folder(destination_path)}
                # Check for name conflicts
                original_name = path.split("/")[-1]
                new_name = original_name
                counter = 1
                while new_name in existing_files:
                    new_name = f"Copy_of_{original_name}" if counter == 1 else f"Copy_({counter})_of_{original_name}"
                    counter += 1

                source_sess.download_file(path, True) 
                            # Get the temporary file path
                os_path = source_sess.get_temp_file_path(original_name)

                # Upload the file to the destination
                print(f"Temporary file path: {os_path}")
                print(f"Uploading to: {destination_path}/{new_name}")
                existing_files.add(new_name)
                return self.current_session.upload_file(os_path, destination_path, new_name)
                
        except Exception as e:
            print(f"Error during copy-paste operation: {e}")
            raise

    @promise
    @enrichable
    def copy_folder(self, path: str, destination_path: str, source_session: str):
        """
        Copy and paste folders to a destination path.
        Delegates the logic to the CloudManager.
        @param folder_path: The path of the folder to copy.
        @param destination_path: The destination folder path.
        @param source_session: The session UID from which the files are copied, 0 if main session
        @return: List of new folder paths in the destination folder.
        """
        try:
            if self.get_current_session() == source_session:
                print(f"Copying folder (same session): {path} to destination: {destination_path}")
                return self.current_session.copy_folder(path, destination_path)
            
            else:
                print(f"Copying folder from different session: {source_session} to {self.get_current_session()}")
                
                source_sess = self.session_manager.get_session(source_session)
                if source_sess is None:
                    source_sess = self.session_manager.main_session

            # List existing items in the destination folder
            existing_items = {item["name"] for item in self.current_session.get_items_in_folder(destination_path)}

            # Check for name conflicts for the folder itself
            original_name = path.split("/")[-1]
            new_folder_name = original_name
            counter = 1
            while new_folder_name in existing_items:
                new_folder_name = f"Copy_of_{original_name}" if counter == 1 else f"Copy_({counter})_of_{original_name}"
                counter += 1

            # Create a temporary directory for the folder
            tmp_dir = self.current_session.get_temp_file_path()
            tmp_dir_folder = self.current_session.get_temp_file_path(original_name)
            # Download the folder to the temporary directory
            print(f"Downloading folder '{path}' to temporary location: {tmp_dir}")
            source_sess.download_folder(path, tmp_dir)

            # Rename the folder in the temporary directory to match the new name
            renamed_tmp_dir_folder = os.path.join(tmp_dir, new_folder_name)
            os.rename(tmp_dir_folder, renamed_tmp_dir_folder)
            print(f"Renamed folder in temporary location to: {renamed_tmp_dir_folder}")

            # Upload the folder from the temporary directory to the destination
            new_folder_path = f"{destination_path}/{new_folder_name}"
            print(f"Uploading folder from temporary location '{renamed_tmp_dir_folder}' to destination: {new_folder_path}")
            self.current_session.upload_folder(renamed_tmp_dir_folder, destination_path)

            print(f"Folder '{path}' successfully copied to '{destination_path}'.")
            if os.path.exists(renamed_tmp_dir_folder):
                shutil.rmtree(renamed_tmp_dir_folder)
                print(f"Temporary directory '{renamed_tmp_dir_folder}' cleaned up.")
            return True
                
        except Exception as e:
            print(f"Error during copy-paste operation: {e}")
            if os.path.exists(renamed_tmp_dir_folder):
                shutil.rmtree(renamed_tmp_dir_folder)
            raise

    @promise
    @enrichable
    def download_folder(self, path):
        """
        Download folder as a ZIP file.
        @param folder_name: The name of the folder to download.
        @return: The path to the ZIP file if successful, False otherwise.
        """

        print(f"Download folder selected: {path}")
        return self.current_session.download_folder(path)


    @promise
    def upload_file(self, file_path, path):
        """
        Upload file function
        @param file_path: the path of the file to upload
        @param path: the path in the cloud to upload the file to
        @return: True if the file was uploaded successfully, False otherwise
        """
        print(f"Upload file selected: {file_path}")
        return self.current_session.upload_file(file_path, path)


    @promise
    def upload_folder(self, folder_path, path):
        """
        Upload folder function
        @param folder_path: the path of the folder to upload
        @param path: the path in the cloud to upload the folder to
        @return: True if the folder was uploaded successfully, False otherwise
        """
        print(f"Upload folder selected {folder_path}")
        return self.current_session.upload_folder(folder_path, path)


    @promise
    @enrichable
    def delete_file(self, path):
        """
        Delete file function
        @param file_id: the id of the file to delete
        @return: True if the file was deleted successfully, False otherwise
        """
        print(f"Delete file selected {path}")
        return self.current_session.delete_file(path)

    @promise
    @enrichable
    def delete_folder(self, path):
        """
        Delete folder function
        @param path: the path of the folder to delete
        @return: True if the folder was deleted successfully, False otherwise
        """
        print(f"Delete folder selected {path}")
        return self.current_session.delete_folder(path)

    
    @promise
    @enrichable
    def rename(self, path: str, new_name: str):
        """
        Rename a file or folder in the cloud storage.
        @param path: The path of the file or folder to rename.
        @param new_name: The new name for the file or folder.
        @return: True if the renaming was successful, raises an exception otherwise.
        """
        print(f"Renaming item at path '{path}' to '{new_name}'")
        return self.current_session.rename_item(path, new_name)

    
    @promise
    def create_folder(self, folder_path):
        print(f"Create folder selected {folder_path}")
        return self.current_session.create_folder(folder_path)

    def get_path_from_searchindex(self, search_index):
        try:
            return self.current_session.object_to_cloudobject(self.search_results[search_index])
        except Exception as e:
            print(f"Error in get_path_from_searchindex: {e}")
            return None

    @promise
    def create_shared_session(self, folder_name : str, emails : list[str], encryption_algo : str, split_algo : str):
        try:
            emails = [email for email in emails if email.strip()]

            shared_with = []
            for email in emails:
                user_dict = {}
                for cloud in self.manager.clouds:
                    user_dict[cloud.get_name()] = email
                shared_with.append(user_dict)
            
            new_session = SharedCloudManager(
                shared_with,
                None,
                list(self.manager.clouds),
                folder_name,
                Split.get_class(split_algo)(),
                self.manager.encrypt.copy(),
                Encrypt.get_class(encryption_algo)()
            )

            self.session_manager.add_session(new_session)
            print(f"New shared session created: {folder_name}")
            return True
        except Exception as e:
            print(f"Error in create_shared_session: {e}")
            return False

    def get_shared_folders(self):
        try:
            # Get the list of pending folders from the session manager
            pending_uids = self.session_manager.pending_folders.keys()

            # Get the list of ready folders (authenticated sessions)
            ready_uids = self.session_manager.sessions.keys()
            
            result = []

            # Add pending folders to the result
            for uid in pending_uids:
                yield {
                    "name": uid,
                    "type": "pending",  # Indicate this is a pending session
                    "uid": uid,
                    "id": uid,
                    "isowner": False  # Pending folders are not owned yet
                }

            # Add ready folders to the result
            for uid in ready_uids:
                yield {
                    "name": uid,
                    "type": "session",  # Indicate this is a shared session
                    "uid": uid,
                    "id": uid,
                    "isowner": self.session_manager.sessions[uid].user_is_owner()
                }

            return result
        except Exception as e:
            print(f"Error in get_shared_folders: {e}")
            return []
    

    #TODO: Advanced sharing options
    """
    def share_file(self):
        pass
    """
    
    @promise
    def leave_shared_folder(self, shared_session_uid):
        """
        Leave a shared folder for the given session name.
        Delegates the logic to SessionManager.
        """
        return self.session_manager.end_session(shared_session_uid)



    @promise
    def delete_shared_folder(self, shared_session_name):
        return self.session_manager.end_session(shared_session_name)


    def get_shared_emails(self, shared_session_name):
        try:
            share = self.session_manager.sessions.get(shared_session_name)
            if share is None:
                print(f"Error: No such session {shared_session_name} exists")
                return None
            return share.get_shared_emails()
        except Exception as e:
            print(f"Error in get_shared_emails: {e}")
            return None
    
    @promise
    def revoke_user_from_share(self, shared_session_name, email_dict):
        """
        unshare emails from given shared folder
        @param folder name (will be convertet to session)
        @param emails list to remove from share 
        TODO: We need to support the option of multiple emails account for the same email.

        As of this POC we are given only one email and support only dropbox and google drive using the same email address!
        """

        share = self.session_manager.sessions.get(shared_session_name)
        if share.user_is_owner():
            return share.revoke_user_from_share(email_dict)

    
    def check_if_user_is_owner(self, shared_session_name):
        """
        Check if the user is the owner of the given session
        @param folder name (will be convertet to session)
        @return: True if the user is the owner, False otherwise
        """
        try:
            share = self.session_manager.sessions.get(shared_session_name)
            if share is None:
                print(f"Error: No such session {shared_session_name} exists")
                return False
            return share.user_is_owner()
        except Exception as e:
            print(f"Error in check_if_user_is_owner: {e}")
            return False
    
    @promise
    def add_users_to_share(self, shared_session_name, emails):
        """
        Share folder with given emails.
        @param shared_session_name: session (folder) name
        @param emails: list of emails to add to share

        TODO: We need to support the option of multiple email accounts for the same email.
        """
        try:
            share = self.session_manager.sessions.get(shared_session_name)
            if share.user_is_owner():
                share_with = []
                for email in emails:
                    user_dict = {}
                    for cloud in self.manager.clouds:
                        user_dict[cloud.get_name()] = email
                    share_with.append(user_dict)
                share.add_users_to_share(share_with)
        except Exception as e:
            raise Exception(f"Error in add_users_to_share: {e}")

    def start_sync_new_sessions_task(self):
        """
        Starts a background task to call sync_new_sessions every X minutes using the thread pool.
        """
        self.stop_event = threading.Event()  # Create a stop event

        def sync_task():
            while not self.stop_event.is_set():  # Check if stop_event is set
                try:
                    print("Running sync_new_sessions...")
                    ret = self.session_manager.sync_new_sessions()
                    if ret:
                        print("New sessions synced successfully.")
                        # Call any registered callbacks
                        for callback in self.sync_future_callbacks:
                            callback()
                        self.sync_future_callbacks.clear() 
                except Exception as e:
                    print(f"Error during sync_new_sessions: {e}")
                # Wait for the next sync interval, but check stop_event periodically
                for _ in range(SYNC_TIME):  # SYNC_TIME is the total wait time in seconds
                    if self.stop_event.is_set():
                        print("Stopping sync_new_sessions task...")
                        return  # Exit the loop if stop_event is set
                    time.sleep(1)  # Sleep for 1 second and check again

        # Submit the sync task to the thread pool
        self.executor.submit(sync_task)
        print("sync_new_sessions task submitted to thread pool.")

    def add_callback_to_sync_task(self, callback):
        """
        Adds a callback to the sync_new_sessions task.
        """
        try:
            if callable(callback):
                self.sync_future_callbacks.append(callback)
                print("Callback added to sync_new_sessions task.")
            else:
                print("Invalid callback provided. Must be callable.")
        except Exception as e:
            print(f"Error in add_callback_to_sync_task: {e}")

    def stop_sync_new_sessions_task(self):
        """
        Stops the sync_new_sessions task.
        """
        try:
            if hasattr(self, 'stop_event'):
                self.stop_event.set()  # Signal the task to stop
                print("sync_new_sessions task stopped.")
        except Exception as e:
            print(f"Error in stop_sync_new_sessions_task: {e}")

def main():
    """
    Encryptosphere main program
    Creates Gateway object and starts the GUI
    """
    gateway = Gateway()
    gui = app.App(gateway)
    gui.mainloop()
    
if __name__=="__main__":
    main()