"""
This is the main file that runs the the entire program
"""
import os

from CloudManager import CloudManager
from modules.Encrypt import *
from modules.Split import *
from modules.CloudAPI import *
from FileDescriptor import FileDescriptor
from SessionManager import SessionManager
import customtkinter as ctk

import utils.DialogBox as DialogBox
import utils.app as app

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

        # Everything here is for testing
        self.manager = CloudManager([DropBox(email)],
                                     "/EncryptoSphere", 
                                     NoSplit(), 
                                     NoEncrypt(), 
                                     FileDescriptor(os.path.join(os.getcwd(),"Test")))
        self.session_manager = SessionManager(self.manager)
        self.manager.authenticate()
        self.manager.upload_file(".\\Test\\uploadme.txt")
        self.manager.fd.sync_to_file()
        return True
    
    def get_files(self):
        print(self.manager.get_file_list())
        return self.manager.get_file_list()
    
    def download_file(self, file_id):
        self.manager.download_file(file_id)
        print("Download file chosen")
        return True #if download succedded else return false
    
    def download_folder(self, folder_id):
        self.manager.download_folder(folder_id)
        return True #if download succedded else return false
    
    def upload_file(self, file_path):
        self.manager.upload_file(file_path)
        return True #if upload succedded else return false
    
    def upload_folder(self, folder_path):
        self.manager.upload_folder(folder_path)
        return True #if upload succedded else return false
    
    def delete_file(self, file_id):
        self.manager.delete_file(file_id)
        print("Delete file chosen")
        return True #if delete succedded else return false
    
    def delete_folder(self, folder_id):
        self.manager.delete_folder(folder_id)
        return True #if delete succedded else return false


def main():
    gateway = Gateway()
    gui = app.App(gateway)
    gui.mainloop()
    
if __name__=="__main__":
    main()

