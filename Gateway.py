"""
This is the main file that runs the the entire program
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

import utils.DialogBox as DialogBox
import app as app


# This is temporary:
from cryptography.fernet import Fernet

class Gateway:
    """
    This class creates EncryptoSphere process and handles UI requests.
    Acts as the api between the UI and the "backend" of the program. 
    """

    def __init__(self):
        self.manager = None
        self.session_manager = None

    # NOTE: This needs to be refactored: function should get an cloud,email list and create the objects based on that
    def authenticate(self, email):
        dropbox1 = DropBox(email)
        #drive1 = GoogleDrive(email)

        # Everything here is for testing
        self.manager = CloudManager(
            [dropbox1],
            "/EncryptoSphere", 
            NoSplit(), 
            NoEncrypt(), 
            FileDescriptor(os.path.join(os.getcwd(),"Test")))
        self.session_manager = SessionManager(Fernet.generate_key(), self.manager)
        self.manager.authenticate()
        
        # dropbox2 = DropBox(email)
        # #Testing shared sessions
        # self.shared_session = SharedCloudManager(
        #     #[{"D":"demek14150@sfxeur.com"}],
        #     None,
        #     [dropbox2],
        #     "/SharedSession", 
        #     NoSplit(), 
        #     NoEncrypt(), 
        #     FileDescriptor(os.path.join(os.getcwd(),"Test\\SharedSession"))
        # )
        # self.shared_session.authenticate()
        self.manager.fd.sync_to_file()
        self.manager.start_sync_thread()
        return True
    
    def get_files(self):
        return self.manager.get_file_list()
    
    def download_file(self, file_id):
        self.manager.download_file(file_id)
        return True # TODO: Handle correctly!!
    
    def download_folder(self, folder_id):
        self.manager.download_folder(folder_id)
        return True # TODO: Handle correctly!!
    
    def upload_file(self, file_path):
        print(f"Upload file selected: {file_path}")
        self.manager.upload_file(file_path)
        return True # TODO: Handle correctly!!
    
    def upload_folder(self, folder_path):
        print(f"Upload folder selected {folder_path}")
        self.manager.upload_folder(folder_path)
        return True # TODO: Handle correctly!!
    
    def delete_file(self, file_id):
        print(f"Delete file selected {file_id}")
        self.manager.delete_file(file_id)
        return True # TODO: Handle correctly!!
    
    def delete_folder(self, folder_id):
        self.manager.delete_folder(folder_id)
        return True # TODO: Handle correctly!!
    
    # TODO: shared session functions
    def create_shared_session(self):
        pass

    def share_file(self):
        pass

    def share_folder(self):
        pass

    def unshare_folder(self):
        pass

    def unshare_file(self):
        pass

    def revoke_user_from_share(self):
        pass

    def add_user_to_share(self):
        pass



def main():
    """
    Encryptosphere main program
    """
    gateway = Gateway()
    gui = app.App(gateway)
    try:
        gui.mainloop()
    finally:    
        gateway.manager.fd.sync_to_file()
    
if __name__=="__main__":
    main()

