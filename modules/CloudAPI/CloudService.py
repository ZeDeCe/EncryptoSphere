from abc import ABC, abstractmethod

class CloudService(ABC):
    class CloudObject:
        """
        Abstract class representing an object in the cloud
        """
        def __init__(self, id : any, path : str, name=None):
            self._id = id
            self.path = path
            self.name = name
            if name == None:
                name = path.split("/")[-1]
                

        def get_path(self):
            return self.path
        
        def get_name(self):
            return self.name
        
        def __str__(self):
            return f"{self.__class__.__name__}: {self._id}, {self.path}"
        
    class Folder(CloudObject):
        """
        This class is the top level folder class that represent folders in a specific cloudservice.
        Can be inherited to add more functionality to the folder objects
        """
        def __init__(self, id : any, path : str, name=None, shared=False):
            super().__init__(id, path, name)
            self.shared = shared
        
        def is_shared(self):
            return self.shared
        

    class File(CloudObject):
        """
        This class is the top level file class that represent files in a specific cloudservice. 
        Can be inherited to add more functionality to the file objects
        Maybe later add more details about files
        """
        pass

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
    
    def is_authenticated(self) -> bool:
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
    def get_children(self, folder : Folder) -> list[File|Folder]:
        """
        Get all file and folder objects that are children of the specified folder
        @param folder the folder object to get the children of
        @return a list of file and folder objects
        """
        pass

    @abstractmethod
    def list_files(self, folder : Folder, filter="") -> list[File]:
        """
        List all files in the folder
        @param folder the folder object, if not specified uses root folder
        @param filter optional to filter the files by name. The function checks if the filename starts with the filter string
        @return a list of all the file names in the folder
        """
        pass

    @abstractmethod
    def upload_file(self, data : bytes, file_name : str, parent : Folder) -> File:
        """
        Upload a file to the cloud storage
        @param data the data to upload
        @param file_name the file name
        @param path the path
        @return the file object if it was uploaded successfully, if fails throws an error
        """
        pass

    @abstractmethod
    def download_file(self, file : File) -> bytes | None:
        """
        Download a file from the cloud storage using
        @param file_name the name of the file
        @param path the path to the file
        @return the data from the file (not a file object), if fails throws an error
        """
        pass

    @abstractmethod
    def delete_file(self, file : File) -> bool:
        """
        Delete a file from the cloud storage
        @param file_path the path to the file in the cloud storage
        @return success, if fails throws an error
        """
        pass

    @abstractmethod
    def get_session_folder(self, name : str) -> Folder:
        """
        Get a normal (none shared) session root folder in a cloud_service
        This is the folder that is used to store all the files in the session
        Generally the name parameter will be the application username for that specific session
        If the folder does not exist, it will be created
        This function should look under the root folder of the cloudservice for a folder with the correct name
        If there are multiple folders with the same path, throws a specific error
        @param name the name of the folder to search for
        @return the folder object to be passed to other folder functions
        """
        pass

    @abstractmethod
    def create_folder(self, name : str, parent : Folder) -> Folder:
        """
        Create a folder in the cloud storage
        @param path the path to create the folder at
        @return the folder object to be passed to other folder functions
        """
        pass

    @abstractmethod
    def share_folder(self, folder : Folder, emails : list[str]) -> Folder:
        """
        Share a file or folder with a user (read/write permissions)
        @param folder the folder object returned from create_folder (or get_folder)
        @param emails a list of emails to share the folder with
        @return the folder object of the now shared folder
        """
        pass

    @abstractmethod
    def create_shared_session(self, name : str, emails : list[str]) -> Folder:
        """
        Creates and shares a folder with a specific list of emails
        This method must create a shared folder in the root directory of the cloudservice
        @param name the name of the folder
        @param emails a list of emails to share with
        @return a folder object
        """
 
    @abstractmethod
    def unshare_folder(self,  folder : Folder) -> None:
        """
        Unshares a folder - makes the folder "unshared", removes anyone shared with it
        @param folder, the folder object
        @return success, if fails throws an error
        """
        pass

    @abstractmethod
    def unshare_by_email(self, folder : Folder, emails : list[str]) -> bool:
        """
        Unshare a folder from a specific emails list
        @param folder the folder object to unshare
        @param emails a list of emails to unshare with
        @return success, if fails throws an error
        """
        pass
    
    @abstractmethod
    def list_shared_folders(self, filter="") -> list[Folder]:
        """
        List all shared folders in all of the cloud
        @return a list of folder objects that represent the shared folders
        """
    
    @abstractmethod
    def get_members_shared(self, folder : Folder) -> list[str] | bool:
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