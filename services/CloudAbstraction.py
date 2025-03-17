import os
import shutil
import uuid

class CloudAbstraction:
    """
    This class is the top application layer for handling actions that relate to files from OS to cloud services
    CloudAbstraction does not handle errors and throws any error to user classes to handle.
    """

    def __split(self, file):
        pass
    def __encrypt(self, file):
        pass
    def __decrypt(self, file):
        pass
    def __merge(self, file):
        pass

    def __create_temp_file(self, os_filepath):
        new_path = os.path.join(os.getenv("ENCRYPTO_ROOT"), "temp", uuid.uuid4())
        shutil.copyfile(os_filepath, new_path)
        return new_path
    
    def __delete_osfile(self, os_filepath):
        pass

    def upload_file(self, os_filepath, path):
        if not os.path.isfile(os_filepath):
            raise OSError()
        
        file = self.__create_temp_file(self, os_filepath)
        # File only gets edited in memory
        self.__encrypt(file)
        split_list = self.__split(file)
        # TODO: finish function

        self.__delete_osfile(file)

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

