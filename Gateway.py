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

import utils.DialogBox as DialogBox
import app as app


# This is temporary:
from cryptography.fernet import Fernet

SYNC_TIME = 90 # 1 min 30 sec

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

    # NOTE: This needs to be refactored: function should get an cloud,email list and create the objects based on that
    def authenticate(self, email):
        master_key = b"11111111111111111111111111111111" # this is temporary supposed to come from login
        dropbox1 = DropBox(email)
        drive1 = GoogleDrive(email)
        encrypt = AESEncrypt()
        encrypt.set_key(encrypt.generate_key_from_key(master_key))
        # Everything here is for testing
        self.manager = CloudManager(
            [drive1,dropbox1],
            "main_session", 
            NoSplit(), 
            encrypt
        )

        self.session_manager = SessionManager(Fernet.generate_key(), self.manager)
        status = self.manager.authenticate()
        self.current_session = self.manager
        self.start_sync_new_sessions_task()
        print(f"Status: {status}")
        return status
    
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
    def sync_fd_to_clouds(self, callback=None):
        if not self.active_fd_sync:
            self.active_fd_sync = True
            print(f"Syncing FD to clouds")
            
            print(f"Syncing FD to clouds, status: {str(True)}")
            return True
        
    @promise    
    def sync_new_sessions(self):
        if not self.active_sessions_sync:
            self.active_sessions_sync = True
            print(f"Searchinng for new sessions...")
            ret = self.session_manager.sync_new_sessions()
            print(f"Finished searching for new sessions")
            self.active_sessions_sync = False
            return ret
        
        
    @promise
    def refresh_shared_folder(self):
        # We don't actually need to do anything, just call get_items_in_folder for that shared folder
        pass

        
    
    @promise
    def download_file(self, file_path):
        """
        Download file function
        @param file_id: the id of the file to download
        @return: True if the file was downloaded successfully, False otherwise
        """
        return self.current_session.download_file(file_path)

    @promise
    def download_folder(self, folder_name):
        """
        Download folder as a ZIP file.
        @param folder_name: The name of the folder to download.
        @return: The path to the ZIP file if successful, False otherwise.
        """
        print(f"Download folder selected: {folder_name}")
        return self.current_session.download_folder(folder_name)
    
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
        return self.session_manager.sessions.keys()

    #TODO: Advanced sharing options
    """
    def share_file(self):
        pass


    def unshare_folder(self):
        pass

    def unshare_file(self):
        pass
    """
    def get_shared_emails(self, folder_path):
        """
        Returns the list of emails that are shared with the given folder
        @param folder_path: the path of the folder to get the shared emails from
        @return: list of emails that are shared with the folder
        """
        share = None
        for root_folder, session in self.session_manager.sessions.items():
            if folder_path == root_folder:
                share = session
        return share.get_shared_emails()
    
    @promise
    def revoke_user_from_share(self, folder_path ,email_dict):
        """
        unshare emails from given shared folder
        @param folder name (will be convertet to session)
        @param emails list to remove from share 
        TODO: We need to support the option of multiple emails account for the same email.

        As of this POC we are given only one email and support only dropbox and google drive using the same email address!

        """
        share = self.session_manager.sessions.get(folder_path)
        share.revoke_user_from_share(email_dict)

    @promise
    def add_users_to_share(self, folder_path ,emails):
        """
        share email with given folder
        @param folder name ==> session
        @param emails list to add to share 
        TODO: We need to support the option of multiple emails account for the same email.
        
        As of this POC we are given only one email and support only dropbox and google drive using the same email address!

        """
        share = self.session_manager.sessions.get(folder_path)
        share_with = []
        for email in emails:
            user_dict = {}
            for cloud in self.manager.clouds:
                user_dict[cloud.get_name()] = email
            share_with.append(user_dict)
        share.add_users_to_share(share_with)

    def start_sync_new_sessions_task(self):
        """
        Starts a background task to call sync_new_sessions every 10 minutes using the thread pool.
        """
        self.stop_event = threading.Event()  # Create a stop event

        def sync_task():
            while not self.stop_event.is_set():  # Check if stop_event is set
                try:
                    print("Running sync_new_sessions...")
                    ret = self.session_manager.sync_new_sessions()
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