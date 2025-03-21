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
        self.cloud_name_list = list(map(lambda c: c.get_name(), self.clouds))

    def __split(self, file, parts):
        return self.split.split(file, parts)
    
    def __merge(self, folder):
        # TODO: finish function
        return self.split.merge_parts()
    
    def __encrypt(self, file):
        self.encrypt.encrypt_file(file)
        return file
    
    def __decrypt(self, file):
        self.encrypt.decrypt_file(file)
        return file

    def __tempfile_from_path(self, os_filepath):
        file = tempfile.TemporaryFile(dir=os.path.dirname(os_filepath))
        with open(os_filepath, "r") as osfile:
            file.write(osfile.read().encode('utf-8'))
        return file

    def authenticate(self, email):
        try:
            for cloud in self.clouds:
                cloud.authenticate_cloud(email)
            return True
        except:
            return False

    # TODO: async this
    def upload_file(self, os_filepath, path=None):
        if not os.path.isfile(os_filepath):
            raise OSError()
        
        data = None
        with open(os_filepath, 'rb') as file:
            data = file.read()

        data = self.__encrypt(data)
        data = self.__split(data, len(self.clouds))
        file_id = self.fd.add_file(
            os.path.basename(os_filepath),
            self.encrypt.get_name(),
            self.split.get_name(),
            self.cloud_name_list
        )
        for i,f in enumerate(data):
            try:
                self.clouds[i].upload_file(f, f"{file_id}", path)
            except:
                print("Failed to upload one of the files")
                self.fd.delete_file(file_id)
                raise Exception()

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

    def delete_file(self, file_id):
        pass

    def delete_folder(self, folder):
        pass

    def get_file_list(self):
        return self.fd.get_file_list()

    def sync_filedescriptor(self):
        """
        When called, uploads the filedescriptor to the clouds
        """
        pass

