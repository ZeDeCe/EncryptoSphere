from abc import ABC, abstractmethod

class CloudService(ABC):

    def __new__(cls, email : str):
        """
        Makes all child objects with the same email a singleton.
        """
        if not hasattr(cls, 'instances'):
            cls.instances = {}
        single = cls.instances.get(email)
        if(single):
            return single
        cls.instances[email] = super(CloudService, cls).__new__(cls)
        return cls.instances[email]

    def __init__(self, email : str):
        """
        Set the email to be the email used for everything
        """
        self.email = email
        self.authenticated = False

    def get_email(self) -> str:
        """
        Return the registered email
        """
        return self.email
    
    def is_authenticated(self):
        """
        Returns the self.authenticated flag if already authenticated
        """
        return self.authenticated
    
    def authenticate_cloud(self) -> bool:
        """
        Authenticate with the cloud service
        Make sure to call this function before overriding
        Make sure to set the self.authenticated flag to True after authentication has occured so that the platform
        won't need to go through authentication twice
        """
        if self.authenticated:
            return True

    @abstractmethod
    def list_files(self, folder=None) -> list:
        """
        List files in the cloud storage, optionally in a specific folder
        """
        pass

    @abstractmethod
    def upload_file(self, data : bytes, file_name : str, path : str) -> bool:
        """
        Upload a file to the cloud storage
        """
        pass

    @abstractmethod
    def download_file(self, file_name : str, path : str) -> bytes:
        """
        Download a file from the cloud storage using
        @param file_name the name of the file
        @param path the path to the file
        @return the data from the file (not a file object)
        """
        pass

    @abstractmethod
    def delete_file(self, file_path : str) -> bool:
        """
        Delete a file from the cloud storage
        @param file_path the path to the file in the cloud storage
        @return success
        """
        pass
    
    @abstractmethod
    def get_folder(self, folder_path : str) -> any:
        """
        Get a folder object from the folder_path if it exists, if not returns None
        @param folder_path the path to the folder to get
        @return the folder object to be passed to other folder functions
        """
        pass

    @abstractmethod
    def create_folder(self, path : str) -> any:
        """
        Create a folder in the cloud storage
        @param path the path to create the folder at
        @return the folder object to be passed to other folder functions
        """
        pass

    @abstractmethod
    def share_folder(self, folder : any, emails : list[str]) -> any:
        """
        Share a file or folder with a user (read/write permissions)
        @param folder the folder object returned from create_folder
        @param emails a list of emails to share the folder with
        @return the folder object of the now shared folder
        """
        pass

    @abstractmethod
    def create_shared_folder(self, path, emails : list[str]) -> any:
        """
        Creates and shares a folder with a specific list of emails
        @param path the path the new folder should be created at
        @param emails a list of emails to share with
        @return a file object of the folder in the respective cloud service
        """
 
    @abstractmethod
    def unshare_folder(self, folder_name):
        """
        Unshare a file completely
        """
        pass

    @abstractmethod
    def unshare_by_email(self, folder : any, emails : list[str]):
        """
        Unshare a folder from a specific emails list
        @param folder the folder object to unshare
        @param emails a list of emails to unshare with
        """
        pass

    @abstractmethod
    def list_shared_files(self):
        """
        List all shared files and folders in the cloud storage
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
         Return the string name of the cloud service
        """
        pass