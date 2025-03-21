"""
This is the main file that runs the the entire program
"""
import os

from CloudAbstraction import CloudAbstraction
from modules.Encrypt import *
from modules.Split import *
from modules.CloudAPI import *
from FileDescriptor import FileDescriptor

import utils.DialogBox as DialogBox
import utils.app as app

def main():
    clouds = [DropBox("/EncryptoSphere")]
    manager = CloudAbstraction(clouds, 
                               NoSplit(), 
                               NoEncrypt(), 
                               FileDescriptor("Test\\EncryptoSphere\\data"))
    try:
        manager.authenticate(DialogBox.input_dialog("EncryptoSphere", "Enter your email: "))
    except:
        print("Failed to authenticate")
        return
    #app.run_app()
    try:
        print(manager.fd)
        manager.upload_file(os.path.join(os.getcwd(), "Test", "uploadme.txt"))
        print(manager.fd)
        manager.upload_file(os.path.join(os.getcwd(), "Test", "uploadme2.txt"))
        print(manager.fd)
        manager.fd.sync_to_file()
    except Exception as e:
        print(e)
        print("Failed to upload file")
        return

    
if __name__=="__main__":
    main()