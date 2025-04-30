from modules.CloudAPI.CloudService import CloudService

class Directory:
    def __init__(self, folders : dict[str | CloudService, CloudService.Folder], path : str):
        """
        {
            "cloud1": folder,
            "cloud2": folder,
            ...
        }
        """
        assert len(folders)>0
        self.folders = {}
        for cloud, item in folders.items():
            if not isinstance(item, CloudService.Folder):
                raise Exception("Trying to create directory with an item that is not a folder!")
            if isinstance(cloud, CloudService):
                self.folders[cloud.get_name()] = item
            elif isinstance(cloud, str):
                self.folders[cloud] = item
            else:
                raise Exception("Cloud key is neither a cloudservice object or a string")
        self.path = path
        self.name = (self.path.split("/")[-1]) if (self.path.split("/")[-1]) != "" else "/"

        self.data = {
            "path": self.path,
            "name": self.name,
            "type": "folder",
            "id": self.path
        }
    
    def get(self, cloud_name : str) -> CloudService.Folder:
        return self.folders[cloud_name]
    
    def get_data(self):
        return self.data
    
    def set_root(self):
        self.path = "/"
        self.name = "/"
        self.data = {
            "name": self.name,
            "path": self.path,
            "id": self.path,
            "type": "folder"
        }
        for cloud, folder in self.folders.items():
            folder.name = "/"

class CloudFile:
    def __init__(self, parts : dict[CloudService, list[CloudService.File]], path):
        """
        @param parts should look like this:
        {
            cloud1: [file_part0, file_part1,...],
            cloud2: [file_part0, file_part1,...],
            ...
        }
        """
        self.parts = parts
        self.path = path
        self.name = (self.path.split("/")[-1]) if (self.path.split("/")[-1]) != "" else "/"
        self.data = {
            "name": self.name,
            "path": self.path,
            "type": "file",
            "id" : self.path
        }

    def get(self, cloud_name : str) -> list[CloudService.File]:
        for cloud in self.parts.keys():
            if cloud.get_name() == cloud_name:
                return self.parts[cloud]
        return None
    
    def get_data(self):
        return self.data