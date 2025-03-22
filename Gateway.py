"""
This is the main file that runs the the entire program
"""
import os

from CloudAbstraction import CloudAbstraction
from modules.Encrypt import *
from modules.Split import *
from modules.CloudAPI import *
from FileDescriptor import FileDescriptor
import customtkinter as ctk

import utils.DialogBox as DialogBox
import utils.app as app

class Gateway:
    """
    This class creates EncryptoSphere process and handles UI requests.
    Acts as the api between the UI and the "backend" of the program. 
    """

    def __init__(self):
        self.clouds = [DropBox()]
        self.manager = CloudAbstraction(self.clouds, "/EncryptoSphere", 
                               NoSplit(), 
                               NoEncrypt(), 
                               FileDescriptor(os.path.join(os.getcwd(),"Test", "MyTest")))
        
    
    def authenticate(self, email):
        self.manager.authenticate(email)
        
        #self.manager.upload_file(r".\Test\test1.txt") #testing only!
        #print(r".\Test\test1.txt") #testing only!
        #self.manager.upload_file(r".\Test\test2.txt") #testing only!
        #self.manager.upload_file(r".\Test\test3.txt") #testing only!
        #self.manager.upload_file(r".\Test\test4.txt") #testing only!
        #self.manager.fd.sync_to_file() #testing only!
        return True # TODO: Handle correctly!!
    
    def get_files(self):
        return self.manager.get_file_list()
    
    def download_file(self, file_id):
        self.manager.download_file(file_id)
        print("Download file chosen")
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
        self.manager.delete_file(file_id)
        print("Delete file chosen")
        return True # TODO: Handle correctly!!
    
    def delete_folder(self, folder_id):
        self.manager.delete_folder(folder_id)
        return True # TODO: Handle correctly!!


def main():
    """
    Encryptosphere main program
    """
    gateway = Gateway()
    gui = app.App(gateway)
    gui.mainloop()
    
if __name__=="__main__":
    main()

