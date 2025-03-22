import os
import tempfile
import hashlib

from modules import Split
from modules import Encrypt
from modules.CloudAPI import CloudService
import FileDescriptor


class CloudManager:
    """
    This class is the top application layer for handling actions that relate to files from OS to cloud services
    CloudManager does not handle errors and throws any error to user classes to handle.
    """
    def __init__(self, clouds : list[CloudService], root : str, split : Split, encrypt : Encrypt, file_descriptor : FileDescriptor):
        """
        Initialize a cloudmanager and a session
        @param clouds the cloud classes to use
        @param root the root directory, must start with /
        @param split the split class to use
        @param encrypt the encrypt class to use
        @param file_descriptor the filedescriptor to use. If none provided, will assume that the session already exists and try syncing it from the cloud
        """
        if root[0]!="/":
            raise Exception("CloudManager: Root direcory must start with /")
        self.split = split
        self.encrypt = encrypt
        self.clouds = clouds
        self.root_folder = f"{os.getenv("ENCRYPTO_ROOT")}{root}"
        self.cloud_name_list = list(map(lambda c: c.get_name(), self.clouds))
        self.fd = file_descriptor if file_descriptor else self.sync_from_clouds()
        self.lock_session()
        

    def lock_session(self):
        """
        Checks if a session file is active on the cloud
        If it is raise error.
        If not then place one to lock the session
        """
        pass

    def __split(self, file, parts):
        return self.split.split(file, parts)
    
    def __merge(self, folder):
        # TODO: finish function
        return self.split.merge_parts()
    
    def _encrypt(self, file):
        self.encrypt.encrypt_file(file)
        return file
    
    def _decrypt(self, file):
        self.encrypt.decrypt_file(file)
        return file

    def __tempfile_from_path(self, os_filepath):
        file = tempfile.TemporaryFile(dir=os.path.dirname(os_filepath))
        with open(os_filepath, "r") as osfile:
            file.write(osfile.read().encode('utf-8'))
        return file

    def authenticate(self):
        try:
            for cloud in self.clouds:
                cloud.authenticate_cloud()
            return True
        except:
            return False

    def upload_file(self, os_filepath, path="/"):
        if not os.path.isfile(os_filepath):
            raise OSError()
        
        data = None
        with open(os_filepath, 'rb') as file:
            data = file.read()
        hash = hashlib.md5(data).hexdigest()
        data = self._encrypt(data)
        data = self.__split(data, len(self.clouds))
        file_id = self.fd.add_file(
            os.path.basename(os_filepath),
            path,
            self.encrypt.get_name(),
            self.split.get_name(),
            self.cloud_name_list,
            hash
        )
        for i,f in enumerate(data):
            try:
                self.clouds[i].upload_file(f, f"{file_id}", self.root_folder)
            except Exception as e:
                print(e)
                self.fd.delete_file(file_id)
                raise Exception("Failed to upload one of the files")
            
    def _upload_replicated(self, file_name, data):
        """
        Encrypts and uploads the given file to all platforms without splitting.
        This function is purposefully limited to only uploading from the root folder
        """
        data = self._encrypt(data)
        for cloud in self.clouds:
            cloud.upload_file(data, file_name, self.root_folder)

    def _download_replicated(self, file_name):
        """
        Downloads and decrypts a the file from the path given if it exists in all clouds
        This function is purposefully limited to only downloading from the root folder
        """
        replicated_files = []
        for cloud in self.clouds:
            replicated_files.append(cloud.download_file(f"{self.root_folder}/{file_name}"))
        return self._check_replicated_integrity(replicated_files)
    
    def _check_replicated_integrity(self, replicated : list[bytes]):
        """
        Checks a list of data for integrity.
        If one of the files does not match the rest, there was a corruption, will return an error status also
        @return a tuple matching (status, data), status is the corruption status, True=Success, False=Corrupted. data is an array of the data if status=False and a single bytes object if status=True
        """
        for data in replicated:
            if data!=replicated[0]:
                return False, replicated
        return True, replicated[0]
        
    # TODO: error handling
    def upload_folder(self, os_folder, path="/"):
        """
        This function uploads an entire folder to the cloud
        Since EncryptoSphere keeps hierarchy only in the FileDescriptor and uploads all files to the same EncryptoSphere
        root folder, we iterate over the folder and upload each file seperately using self.upload_file
        @param os_folder the folder path on the OS to upload
        @param path the root path for the folder in encryptosphere hierarchy
        """
        os_folder = os.path.abspath(os_folder)
        folder_name = os.path.basename(os_folder)
        if path[-1] !="/":
            path = f"{path}/"
        for root, _, files in os.walk(os_folder):
            root_arr = root.split(os.sep)
            root_arr = root_arr[root_arr.index(folder_name):]
            encrypto_root = "/".join(root_arr)
            for file in files:
                self.upload_file(os.path.join(root,file), f"{path}{encrypto_root}")
        # can add yield here to tell which files have been uploaded

    def download_file(self, file_id):
        """
        Downloads a file from the various clouds
        file_id is a FileDescriptor ID of the file.
        Make sure to check if the clouds of this object exist in the "parts" array
        """
        pass

    def download_folder(self, folder_name):
        """
        Using filedescriptor functions, gathers all files under the folder_name and then calls self.download
        on all of those files. Constructs them as the hierarchy in the filedescriptor on the OS.
        """
        pass

    def delete_file(self, file_id):
        """
        Deletes a specific file from file ID using the filedescriptor
        @param file_id the file id to delete
        """
        pass

    def delete_folder(self, folder_path):
        """
        Given a path in EncryptoSphere (/EncryptoSphere/...), deletes all files with that path name
        @param folder_path the path to the folder in the file descriptor
        """
        pass

    def get_file_list(self):
        return self.fd.get_file_list()

    def sync_to_clouds(self):
        """
        Uploads the filedescriptor to the clouds encrypted using self.encrypt
        This function should use upload_replicated
        """
        pass

    def sync_from_clouds(self):
        """
        Downloads the filedescriptor from the clouds, decrypts it using self.encrypt, and sets it as this object's file descriptor
        This function should use download_replicated
        """
        pass

