from abc import ABC, abstractmethod

class CloudService(ABC):
    def __init__(self, email : str):
        """
        Set the email to be the email used for everything
        """
        self.email = email

    def get_email(self) -> str:
        """
        Return the registered email
        @return the email
        """
        return self.email

    @abstractmethod
    def authenticate_cloud(self) -> bool:
        """
        Authenticate with the cloud service
        @return success, if fails throws an error
        """
        pass

    @abstractmethod
    def list_files(self, folder='/') -> list:
        """
        List files in the cloud storage, optionally in a specific folder object
        @param folder the folder object, if not specified uses root folder
        @return a list of all the files in the folder
        """
        pass

    @abstractmethod
    def upload_file(self, data : bytes, file_name : str, path : str) -> bool:
        """
        Upload a file to the cloud storage
        @param data the data to upload
        @param file_name the file name
        @param path the path
        @return success, if fails throws an error
        """
        pass

    @abstractmethod
    def download_file(self, file_name : str, path : str) -> bytes:
        """
        Download a file from the cloud storage using
        @param file_name the name of the file
        @param path the path to the file
        @return the data from the file (not a file object), if fails throws an error
        """
        pass

    @abstractmethod
    def delete_file(self, file_name : str, path : str) -> bool:
        """
        Delete a file from the cloud storage
        @param file_path the path to the file in the cloud storage
        @return success, if fails throws an error
        """
        pass
    
    @abstractmethod
    def get_folder(self, path : str) -> any:
        """
        Get a folder object from the path if it exists, if not throws an error
        @param path the path to the folder to get
        @return the folder object to be passed to other folder functions
        """
        pass

    @abstractmethod
    def get_folder_path(self, folder : any) -> str:
        """
        @param folder a folder object returned from one of the folder functions
        @return the path of the folder object
        """

    @abstractmethod
    def create_folder(self, path : str) -> any:
        """
        Create a folder in the cloud storage
        @param path the path to create the folder at
        @return the folder object to be passed to other folder functions
        """
        pass

    @abstractmethod
    def share(self, folder : any, emails : list[str]) -> any:
        """
        Share a file or folder with a user (read/write permissions)
        @param folder the folder object returned from create_folder (or get_folder)
        @param emails a list of emails to share the folder with
        @return the folder object of the now shared folder
        """
        pass
 
    @abstractmethod
    def unshare_folder(self, folder : any) -> bool:
        """
        Unshares a folder - makes the folder "unshared", removes anyone shared with it
        @param folder, the folder object
        @return success, if fails throws an error
        """
        pass

    @abstractmethod
    def unshare_by_email(self, folder : any, emails : list[str]) -> bool:
        """
        Unshare a folder from a specific emails list
        @param folder the folder object to unshare
        @param emails a list of emails to unshare with
        @return success, if fails throws an error
        """
        pass

    @abstractmethod
    def list_shared_files(self, folder=None):
        """
        List all shared files and folders in the cloud storage
        @param folder, optional, the folder object to look into
        @return a list of shared file objects
        """
        pass
    
    @abstractmethod
    def list_shared_folders(self):
        """
        List all shared folders in all of the cloud
        @return a list of folder objects that represent the shared folders
        """

    @abstractmethod
    def get_name(self) -> str:
        """
         @return the string name of the cloud service
        """
        pass