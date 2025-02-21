from abc import ABC, abstractmethod

class CloudService(ABC):
    @abstractmethod
    def authenticate_cloud(self):
        #Authenticate with the cloud service
        pass

    @abstractmethod
    def list_files(self):
        #List files in the cloud storage, optionally in a specific folder
        pass

    @abstractmethod
    def upload_file(self, file_path):
        #Upload a file to the cloud storage
        pass

    @abstractmethod
    def download_file(self, file_name):
        #Download a file from the cloud storage
        pass

    @abstractmethod
    def delete_file(self, file_name):
        #Download a file from the cloud storage
        pass
    @abstractmethod
    def create_folder(self):
        #Create a folder in the cloud storage
        pass

    @abstractmethod
    def share(self, folder, emails):
        #Share a file or folder with a user (read/write permissions)
        pass
 
    @abstractmethod
    def unshare_folder(self, folder):
        #Unshare a file or folder from a user
        pass

    @abstractmethod
    def unshare_by_email(self, folder, emails):
        #Unshare a file or folder from a user
        pass

    @abstractmethod
    def list_shared_files(self):
        #List all shared files and folders in the cloud storage
        pass
