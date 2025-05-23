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
from FileDescriptor import FileDescriptor
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

import utils.DialogBox as DialogBox
import app as app


# This is temporary:
from cryptography.fernet import Fernet

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
        self.autenticated_clouds = []
        self.email = None
        self.metadata_exists = False
        

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
            return future
        return wrapper

    def is_metadata_exists(self, cloud : CloudService):
        return CloudManager.is_metadata_exists(cloud, MAIN_SESSION)

    def get_metadata_exists(self):
        return self.metadata_exists
    
    def get_algorithms(self):
        """
        Returns the list of algorithms
        """
        return Encrypt.get_classes(), Split.get_classes()
    
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
        for cloud_class in supported_clouds:
            cloud = cloud_class(self.email)
            if cloud.authenticate_by_token():
                autenticated_clouds.append(cloud)
                if not self.metadata_exists:
                    self.metadata_exists = self.is_metadata_exists(cloud)    
        self.autenticated_clouds = autenticated_clouds
        return autenticated_clouds


    def set_email(self, email: str):
        assert self.email is None
        self.email = email


    
    def get_authenticated_clouds(self):
        """
        Returns the list of authenticated clouds
        """
        return self.autenticated_clouds
    
    @promise
    def app_authenticate(self, password: str):
        """
        Authenticates the application using the provided password and cloud list.
        Fails if the password is incorrect or if metadata is invalid.
        """
        # Step 1: Load metadata using a temporary encryptor (will be replaced later)
        temp_encrypt = AESEncrypt()  # Temporary encryptor just to allow metadata loading
        manager = CloudManager(
            self.autenticated_clouds,
            MAIN_SESSION,
            ShamirSplit(),  # Temporary, real one will be created after metadata
            temp_encrypt
        )
        manager.load_metadata()

        # Step 2: Extract metadata and relevant configuration
        metadata = manager.metadata
        encryption_type = metadata.get("encrypt")
        split_type = metadata.get("split")
        auth_encrypted = bytes.fromhex(metadata.get("auth_encrypted"))
        auth_hash = metadata.get("auth_hash")

        salt_hex = metadata.get("salt")
        if not salt_hex:
            raise ValueError("Missing salt in metadata")
        salt = bytes.fromhex(salt_hex)

        # Step 3: Generate encryption key from password and salt
        encryption_class = Encrypt.get_class(encryption_type)
        encryptor = encryption_class()
        password_key = encryptor.create_key_from_password(password, salt)
        key = encryptor.generate_key_from_key(password_key)
        encryptor.set_key(key)

        # Step 4: Try to decrypt and validate password
        try:
            plaintext = encryptor.decrypt(auth_encrypted)
        except Exception:
            raise ValueError("Invalid password")

        if hashlib.sha256(plaintext).hexdigest() != auth_hash:
            raise ValueError("Invalid password")

        # Step 5: Create the real manager with the correct encryptor
        self.manager = CloudManager(
             self.autenticated_clouds,
            MAIN_SESSION,
            Split.get_class(split_type)(),
            encryptor
        )

        # Step 6: Regular session setup (same as your original logic)
        self.session_manager = SessionManager(Fernet.generate_key(), self.manager)
        status = self.manager.authenticate()
        self.current_session = self.manager
        self.start_sync_new_sessions_task()
        print(f"Status: {status}")
        return status


    def create_account(self, password: str, clouds: list) -> bool:
        """
        Creates a new account by initializing cloud metadata if it doesn't already exist.
        Returns True if account created successfully.
        Raises descriptive exceptions if something fails.
        """
        if not password or len(password) < 6:
            raise ValueError("Password is too short")

        if not clouds:
            raise ValueError("No cloud services provided")

        # check if metadata already exists
        try:
            temp_encryptor = AESEncrypt()
            manager = CloudManager(
                clouds,
                MAIN_SESSION,
                ShamirSplit(),
                temp_encryptor
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize CloudManager: {e}")

        try:
            existing = manager._download_replicated("$META")
        except Exception:
            raise RuntimeError("Could not access cloud to check for existing account")

        if existing is not None:
            raise Exception("Account already exists – metadata found in cloud")

        # Generate salt and encryption key
        try:
            salt = os.urandom(16)
            key = temp_encryptor.create_key_from_password(password, salt)
        except Exception as e:
            raise RuntimeError(f"Key generation failed: {e}")

        # Build metadata
        metadata = {
            "encrypt": temp_encryptor.get_name(),
            "split": "shamir",
            "order": [cloud.get_name() for cloud in clouds]
        }

        try:
            metadata = self.login_manager.add_auth_to_metadata(
                key, metadata, temp_encryptor.get_name(), salt
            )
        except Exception as e:
            raise RuntimeError(f"Failed to generate authentication metadata: {e}")

        # Upload metadata
        try:
            manager._upload_replicated("$META", json.dumps(metadata).encode("utf-8"))
        except Exception as e:
            raise RuntimeError(f"Failed to upload metadata to cloud: {e}")

        return True

    def get_clouds(self):
        return CloudService.get_cloud_classes()
        

    def change_session(self, uid=None):
        """
        Change the current session to the one specified by path
        @param path: the path to the session to change to
        """
        if uid:
           self.current_session = self.session_manager.get_session(uid)
        else:
            self.current_session = self.session_manager.main_session
    
    def get_items_in_folder(self, path="/"):
        """
        @param path: the path to the folder
        @return: Yielded iterable (generator) for every file in the current session in the folder given
        """
        return self.current_session.get_items_in_folder(path)
    
    @promise
    def get_items_in_folder_async(self, path="/"):
        return self.current_session.get_items_in_folder(path)
    
    @promise
    def get_search_results_async(self, search_string):
        """
        @param path: the path to the folder
        @return: Yielded iterable (generator) for every file in the current session in the folder given
        """
        #return self.current_session.get_search_results(search_string)
        print(f"Searching for {search_string}")
        return iter([])
    
    @promise
    def sync_session(self):
        print("Refresh button clicked")
        ret = self.session_manager.sync_new_sessions()
        print(f"Finished refreshing")
        return ret
    

    @promise
    def refresh_shared_folder(self):
        # We don't actually need to do anything, just call get_items_in_folder for that shared folder
        pass

        
    @promise
    def open_file(self, file_path):
        """
        Open file function
        @param file_id: the id of the file to open
        @return: True if the file was opened successfully, False otherwise
        """
        print(f"Open file selected: {file_path}")
        return self.current_session.open_file(file_path)
    

    @promise
    def download_file(self, file_path):
        """
        Download file function
        @param file_id: the id of the file to download
        @return: True if the file was downloaded successfully, False otherwise
        """
        return self.current_session.download_file(file_path)

    @promise
    def download_folder(self, folder_path):
        """
        Download folder as a ZIP file.
        @param folder_name: The name of the folder to download.
        @return: The path to the ZIP file if successful, False otherwise.
        """
        print(f"Download folder selected: {folder_path}")
        return self.current_session.download_folder(folder_path)
    
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
    def delete_file(self, file_path):
        """
        Delete file function
        @param file_id: the id of the file to delete
        @return: True if the file was deleted successfully, False otherwise
        """
        print(f"Delete file selected {file_path}")
        return self.current_session.delete_file(file_path)

    @promise
    def delete_folder(self, folder_path):
        """
        Delete folder function
        @param path: the path of the folder to delete
        @return: True if the folder was deleted successfully, False otherwise
        """
        print(f"Delete folder selected {folder_path}")
        return self.current_session.delete_folder(folder_path)
    
    @promise
    def create_folder(self, folder_path):
        """
        Create folder function
        @param folder_name: the name of the folder to create
        @param path: the path in the cloud to create the folder in
        @return: True if the folder was created successfully, False otherwise
        """
        print(f"Create folder selected {folder_path}")
        return self.current_session.create_folder(folder_path)
    
    @promise
    def create_shared_session(self, folder_name, emails):
        """
        Create new shared session
        @param folder name
        @param emails list of the share members
        TODO: At the next stage we want to let the user pick on which clouds he want to do the share
        also, we need to support the option of multiple emails account for the same email.

        As of this POC we are given only one email and support only dropbox and google drive using the same email address!

        """

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
            self.manager.split.copy(),
            self.manager.encrypt.copy(),
        )

        self.session_manager.add_session(new_session)
        print(f"New shared session created: {folder_name}")
        return True


    def get_shared_folders(self):
        """
        Returns the list of shared folders
        @return: list of shared folders names
        """
        ##self.executor.submit(self.session_manager.sync_new_sessions) # this will probably slow everything down but needed
        #res = self.session_manager.sync_new_sessions()
        # Get the list of pending folders from the session manager
        pending_uids = self.session_manager.get_pending_folders()

        # Get the list of ready folders (authenticated sessions)
        ready_uids = self.session_manager.sessions.keys()
        
        result = []

        # Add pending folders to the result
        for uid in pending_uids:
            result.append({
                "name": uid,
                "type": "pending",  # Indicate this is a pending session
                "uid": uid,
                "isowner": False  # Pending folders are not owned yet
            })

        # Add ready folders to the result
        for uid in ready_uids:
            result.append({
                "name": uid,
                "type": "session",  # Indicate this is a shared session
                "uid": uid,
                "isowner": self.session_manager.sessions[uid].user_is_owner()
            })

        return result
    

    #TODO: Advanced sharing options
    """
    def share_file(self):
        pass
    """
    
    @promise
    def leave_shared_folder(self, shared_session_name):
        raise NotImplementedError("Leaving shared folders is not implemented yet")
        

    @promise
    def delete_shared_folder(self, shared_session_name):
        self.session_manager.end_session(shared_session_name)
    

    def get_shared_emails(self, shared_session_name):
        """
        Returns the list of emails that are shared with the given folder
        @param folder_path: the path of the folder to get the shared emails from
        @return: list of emails that are shared with the folder
        """
        share = self.session_manager.sessions.get(shared_session_name)
        if share is None:
            print(f"Error: No such session {shared_session_name} exists")
            return None
        return share.get_shared_emails()
    
    @promise
    def revoke_user_from_share(self, shared_session_name ,email_dict):
        """
        unshare emails from given shared folder
        @param folder name (will be convertet to session)
        @param emails list to remove from share 
        TODO: We need to support the option of multiple emails account for the same email.

        As of this POC we are given only one email and support only dropbox and google drive using the same email address!

        """
        share = self.session_manager.sessions.get(shared_session_name)
        if share.user_is_owner():
            share.revoke_user_from_share(email_dict)
    
    def check_if_user_is_owner(self, shared_session_name):
        """
        Check if the user is the owner of the given session
        @param folder name (will be convertet to session)
        @return: True if the user is the owner, False otherwise
        """
        share = self.session_manager.sessions.get(shared_session_name)
        if share is None:
            print(f"Error: No such session {shared_session_name} exists")
            return False
        return share.user_is_owner()
    
    @promise
    def add_users_to_share(self, shared_session_name ,emails):
        """
        share email with given folder
        @param folder name ==> session
        @param emails list to add to share 
        TODO: We need to support the option of multiple emails account for the same email.
        
        As of this POC we are given only one email and support only dropbox and google drive using the same email address!

        """
        share = self.session_manager.sessions.get(shared_session_name)
        if share.user_is_owner():
            share_with = []
            for email in emails:
                user_dict = {}
                for cloud in self.manager.clouds:
                    user_dict[cloud.get_name()] = email
                share_with.append(user_dict)
            share.add_users_to_share(share_with)

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
        if callable(callback):
            self.sync_future_callbacks.append(callback)
            print("Callback added to sync_new_sessions task.")
        else:
            print("Invalid callback provided. Must be callable.")

    def stop_sync_new_sessions_task(self):
        """
        Stops the sync_new_sessions task.
        """
        if hasattr(self, 'stop_event'):
            self.stop_event.set()  # Signal the task to stop
            print("sync_new_sessions task stopped.")            


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