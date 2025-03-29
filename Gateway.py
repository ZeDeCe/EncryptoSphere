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
        master_key = b"11111111111111111111111111111111" # this is temporary supposed to come from login
        dropbox1 = DropBox(email)
        drive1 = GoogleDrive(email)
        encrypt = AESEncrypt()
        encrypt.set_key(encrypt.generate_key_from_key(master_key))
        # Everything here is for testing
        self.manager = CloudManager(
            [drive1, dropbox1],
            "/EncryptoSphere", 
            ShamirSplit(), 
            encrypt
        )

        self.session_manager = SessionManager(Fernet.generate_key(), self.manager)
        status = self.manager.authenticate()
        print(f"Status: {status}")
        self.current_session = self.manager
        self.session_manager.sync_new_sessions() # this can take a long time, look at the output window
        return status
    
    def change_session(self, path=None):
        """
        Change the current session to the one specified by path
        @param path: the path to the session to change to
        """
        if path:
           self.current_session = self.session_manager.get_session(path)
        else:
            self.current_session = self.session_manager.main_session
    
    """ 
    def get_files(self):
        return self.current_session.get_file_list()
    """ 
    
    def get_files(self, path="/"):
        """
        @return: list of files in the current session in the FD format
        """
        return self.manager.get_items_in_folder(path)
    
    def download_file(self, file_id):
        """
        Download file function
        @param file_id: the id of the file to download
        @return: True if the file was downloaded successfully, False otherwise
        """
        return self.current_session.download_file(file_id)

    """
    def download_folder(self, folder_id):
        self.current_session.download_folder(folder_id)
        return True # TODO: Handle correctly!!
    """
    
    def upload_file(self, file_path, path):
        """
        Upload file function
        @param file_path: the path of the file to upload
        @param path: the path in the cloud to upload the file to
        @return: True if the file was uploaded successfully, False otherwise
        """
        print(f"Upload file selected: {file_path}")
        return self.current_session.upload_file(file_path, path)

    
    def upload_folder(self, folder_path, path):
        """
        Upload folder function
        @param folder_path: the path of the folder to upload
        @param path: the path in the cloud to upload the folder to
        @return: True if the folder was uploaded successfully, False otherwise
        """
        print(f"Upload folder selected {folder_path}")
        return self.current_session.upload_folder(folder_path, path)

    
    def delete_file(self, file_id):
        """
        Delete file function
        @param file_id: the id of the file to delete
        @return: True if the file was deleted successfully, False otherwise
        """
        print(f"Delete file selected {file_id}")
        return self.current_session.delete_file(file_id)

    
    def delete_folder(self, path):
        """
        Delete folder function
        @param path: the path of the folder to delete
        @return: True if the folder was deleted successfully, False otherwise
        """
        return self.current_session.delete_folder(path)
    

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
            self.manager.clouds,
            f"/{folder_name}_ENCRYPTOSPHERE_SHARE", 
            self.manager.split,
            self.manager.encrypt, 
        )

        self.session_manager.add_session(new_session)
        print(f"New shared session created: {folder_name}")
        return True


    def get_shared_folders(self):
        """
        Returns the list of shared folders
        @return: list of shared folders names
        """
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

    def revoke_user_from_share(self, folder_path ,emails):
        """
        unshare emails from given shared folder
        @param folder name (will be convertet to session)
        @param emails list to remove from share 
        TODO: We need to support the option of multiple emails account for the same email.

        As of this POC we are given only one email and support only dropbox and google drive using the same email address!

        """
        share = None
        for session in self.session_manager.sessions:
            if folder_path ==  session.root_folder:
                share = session
        unshare_with = []
        for email in emails:
            user_dict = {}
            for cloud in self.manager.clouds:
                user_dict[cloud.get_name()] = email
            unshare_with.append(user_dict)
        share.revoke_user_from_share(unshare_with)

    def add_user_to_share(self, folder_path ,emails):
        """
        share email with given folder
        @param folder name ==> session
        @param emails list to add to share 
        TODO: We need to support the option of multiple emails account for the same email.
        
        As of this POC we are given only one email and support only dropbox and google drive using the same email address!

        """
        share = None
        for session in self.session_manager.sessions:
            if folder_path ==  session.root_folder:
                share = session
        share_with = []
        for email in emails:
            user_dict = {}
            for cloud in self.manager.clouds:
                user_dict[cloud.get_name()] = email
            share_with.append(user_dict)
        share.revoke_user_from_share(share_with)


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

