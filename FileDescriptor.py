import os
import json

"""
File descriptors look like this:
FD:
[
    id = {
        name, 
        upload_date, 
        edit_date, 
        encryption_algo, 
        splitting_algo, 
        shared_with, 
        encryption_salt,
        file_hash,
        path,
        [file_parts]
    }
]
"""


class FileDescriptor:
    # class LFUCache:
    #     """
    #     The LFU cache of the FileDescriptor class
    #     This cache gets called on files that are being accessed to save their metadata
    #     for frequent use
    #     """
    #     def __init__(self, capacity):
    #         self.capacity = capacity
    #         self.cache = []

    #     def get(self, file_id):
    #         pass

    #     def put(self, data):
    #         pass

    def __init__(self, root):
        """
        Construct a new FileDescriptor
        """
        # root is the "root folder" that this filedescriptor is based on
        # a filedescriptor represents a filesystem, will be used in sharing as a file system for shared folders
        self.root = root
        self.file = open(os.path.join(os.getenv("ENCRYPTO_ROOT"), self.root, "FD"), "rw") # TODO: Error handling
        self.files = {}
        self.last_id = 0

    def __init__(self, filedescriptor):
        """
        Creates a new FileDescriptor object from an existing FileDescriptor file
        Creating a filedescriptor with an invalid filedescriptor file will raise an OSError
        @param filedescriptor the path to the filedescriptor in the OS
        """
        if not os.path.isfile(filedescriptor):
            raise OSError()
        self.file = open(filedescriptor, "r+")
        self.root = os.path.dirname(filedescriptor)
        self.files = json.load(self.file)
        self.last_id = self.files["__metadata"].last_id
        
    def __del__(self):
        self.file.close()

    def add_file(self, data):
        """
        Add a new file to the filedescriptor listing
        @return the file_id
        """
        # TODO: check if data is valid
        self.last_id += 1
        self.files[f"{self.last_id}"] = data

    def delete_file(self, file_id):
        """
        Delete a file listing for a file that does not exist anymore
        @return the file metadata that got deleted
        """
        self.files.pop(file_id)

    def edit_file(self, file_id, data):
        """
        Edits the file metadata of file_id with the new data in data
        @return the file_id
        """
        file = self.files[file_id]
        for key, val in data.items():
            file[key] = val

    def get_file_data(self, file_id):
        """
        Returns the data of a file_id as an array that can be edited and sent to edit_file
        """
        return self.files[file_id]

    def get_file_list(self):
        """
        Returns the list of all files in the FileDescriptor
        """
        return list(map(lambda f: f["name"],self.files))

    def get_path(self):
        """
        Returns the path of the filedescriptor
        """
        return os.path.realpath(self.file.name)
    
    def sync_to_file(self):
        """
        Sync the filemapping to disk
        """
        self.file.write(json.dump(self.files))
