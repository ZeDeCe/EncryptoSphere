import os
import tempfile

from modules import Split
from modules import Encrypt
import FileDescriptor
from modules.CloudAPI import CloudService

class CloudAbstraction:
    """
    This class is the top application layer for handling actions that relate to files from OS to cloud services
    CloudAbstraction does not handle errors and throws any error to user classes to handle.
    """

    def __init__(self, clouds, split : Split, encrypt : Encrypt, file_descriptor : FileDescriptor):
        self.split = split
        self.encrypt = encrypt
        self.fd = file_descriptor
        self.clouds = clouds

    def __split(self, file, parts):
        return self.split.split_file(file, parts)
    
    def __merge(self, folder):
        output = os.path.join(folder,"merged")
        self.split.merge_parts(folder, output)
        return output
    
    def __encrypt(self, file):
        self.encrypt.encrypt_file(file)
        return file
    
    def __decrypt(self, file):
        self.encrypt.decrypt_file(file)
        return file

    def __tempfile_from_path(self, os_filepath):
        file = tempfile.TemporaryFile()
        with open(os_filepath, "r") as osfile:
            for line in osfile:
                file.write(line)
        return file

    def authenticate(self, email):
        for cloud in self.clouds:
            cloud.authenticate_cloud(email)

    # TODO: async this
    def upload_file(self, os_filepath, path):
        if not os.path.isfile(os_filepath):
            raise OSError()
        
        with self.__tempfile_from_path(self, os_filepath) as file:
            self.__encrypt(file)
            split_folder = self.__split(file, len(self.clouds))
            # TODO: add filedescriptor
            for i,f in enumerate(os.listdir(split_folder)):
                self.clouds[i].upload_file(f)

    # TODO: error handling
    def upload_folder(self, folder):
        """
        This function uploads an entire folder to the cloud
        Since EncryptoSphere keeps hierarchy only in the FileDescriptor and uploads all files to the same EncryptoSphere
        root folder, we iterate over the folder and upload each file seperately using self.upload_file
        """
        for root, _, files in os.walk(folder):
            path = '/'.join(root.split(os.sep))
            for file in files:
                self.upload_file(self, file, path)
        # can add yield here to tell which files have been uploaded

    def download_file(self, file_id):
        """
        Downloads a file from the various clouds
        file_id is a FileDescriptor ID of the file.
        """
        pass

    def download_folder(self, folder_name):
        """
        Using filedescriptor functions, gathers all files under the folder_name and then calls self.download
        on all of those files. Constructs them as the hierarchy in the filedescriptor.
        """
        pass

    def sync_filedescriptor(self):
        """
        When called, uploads the filedescriptor to the clouds
        """
        pass

