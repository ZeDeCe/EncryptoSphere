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
            NoEncrypt()
        )
        self.session_manager = SessionManager(Fernet.generate_key(), self.manager)
        status = self.manager.authenticate()
        self.current_session = self.manager 
       
        # dropbox2 = DropBox(email)
        # #Testing shared sessions
        # self.shared_session = SharedCloudManager(
        #     #[{"D":"pokaya6659@cybtric.com"}],
        #     None,
        #     [dropbox2],
        #     "/SharedSession", 
        #     NoSplit(), 
        #     NoEncrypt(), 
        # )
        # self.shared_session.authenticate()
        # self.shared_session.upload_file(".\\Test\\uploadme.txt")
        return status
    
    def change_session(self, path=None):
        if path:
           self.current_session = self.session_manager.get_session(path)
        else:
            self.current_session = self.session_manager.main_session
        
    def get_files(self):
        return self.current_session.get_file_list()
    
    def download_file(self, file_id):
        self.current_session.download_file(file_id)
        return True # TODO: Handle correctly!!
    
    def download_folder(self, folder_id):
        self.current_session.download_folder(folder_id)
        return True # TODO: Handle correctly!!
    
    def upload_file(self, file_path):
        print(f"Upload file selected: {file_path}")
        self.current_session.upload_file(file_path)
        return True # TODO: Handle correctly!!
    
    def upload_folder(self, folder_path):
        print(f"Upload folder selected {folder_path}")
        self.current_session.upload_folder(folder_path)
        return True # TODO: Handle correctly!!
    
    def delete_file(self, file_id):
        print(f"Delete file selected {file_id}")
        self.current_session.delete_file(file_id)
        return True # TODO: Handle correctly!!
    
    def delete_folder(self, folder_id):
        self.current_session.delete_folder(folder_id)
        return True # TODO: Handle correctly!!
    
    # TODO: shared session functions
    def create_shared_session(self, folder_name, emails):
        """
        Create new shared session
        @param folder name
        @param emails list of the share members
        TODO: At the next stage we want to let the user pick on which clouds he want to do the share
        also, we need to support the option of multiple emails account for the same email.
        As of this POC we are given only one email and support only dropbox and google drive using the same email address.
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
             NoSplit(), 
             NoEncrypt(), 
        )
        self.session_manager.add_session(new_session)
        return True

    def get_shared_folders(self):
        folders = {}
        for session in self.session_manager.sessions:
            folder_name =  session.root_folder
            files_of_folder = session.get_file_list() # Sould return tuple of files and folders under the curr folder
            folders[folder_name] = files_of_folder
        return folders

    #def share_file(self):
    #    pass

    #def share_folder(self):
    #    pass

    def unshare_folder(self):
        pass

    #def unshare_file(self):
    #    pass

    def revoke_user_from_share(self, folder_path ,emails):
        """
        unshare emails from given shared folder
        @param folder name (will be convertet to session)
        @param emails list to remove from share 
        TODO: we need to support the option of multiple emails account for the same email.
        As of this POC we are given only one email and support only dropbox and google drive using the same email address.
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
        @param folder name (will be convertet to session)
        @param emails list to add to share 
        TODO: we need to support the option of multiple emails account for the same email.
        As of this POC we are given only one email and support only dropbox and google drive using the same email address.
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
    """
    gateway = Gateway()
    gui = app.App(gateway)
    gui.mainloop()
    
if __name__=="__main__":
    main()

