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
        cls.instances[email].authenticated = False
        cls.instances[email].email = email
        return cls.instances[email]

    def __init__(self, email : str):
        """
        Currently everything is setup in the __new__ function, individual classes can set
        their variables in their __new__ functions as well.
        Do not set up variables here that don't need to be overriden
        """
        pass

    def get_email(self) -> str:
        """
        Return the registered email
        @return the email
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
        @return success, if fails throws an error
        """
        return self.authenticated

    @abstractmethod
    def list_files(self, folder='/') -> list:
        """
        List files in the cloud storage, optionally in a specific folder object
        @param folder the folder object, if not specified uses root folder
        @return a list of all the file names in the folder
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
    def download_file(self, file_name : str, path : str) -> bytes | None:
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
    def share_folder(self, folder : any, emails : list[str]) -> any:
        """
        Share a file or folder with a user (read/write permissions)
        @param folder the folder object returned from create_folder (or get_folder)
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
        @return a folder object
        """
        pass
 
    @abstractmethod
    def unshare_folder(self, folder):
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
        @return a list of shared file names
        """
        pass
    
    @abstractmethod
    def list_shared_folders(self):
        """
        List all shared folders in all of the cloud
        @return a list of folder objects that represent the shared folders
        """
        pass
    
    @abstractmethod
    def get_members_shared(self, folder : any) -> list[str] | bool:
        """
        Returns a list of emails that the folder is shared with if shared, and false if not shared
        @param folder the folder object
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
         @return the string name of the cloud service
        """
        pass