import os
import json
from datetime import datetime, timezone

"""
File descriptors look like this:
FD:
{
    id = {
        name, The name of the file
        path, The path of the file in EncryptoSphere
        upload_date, The upload date
        edit_date, The edit date
        e_alg, The encryption algorithm used to encrypt the file
        s_alg, The splitting algorithm used to split the file
        shared_with, Who it is shared with
        encryption_salt, The encryption salt
        file_hash, The MD5 hash of the file
        parts = [file_parts] Ordered list of file parts (e.g [Google, DropBox])
    }
}
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
        Creates a new FileDescriptor object from an existing FileDescriptor file
        Creating a filedescriptor with an invalid filedescriptor file will raise an OSError
        @param root the path of the filedescriptor in the os
        """
        try:
            if not os.path.exists(root):
                os.makedirs(root)
        except:
            raise OSError("Root folder given for FD is invalid")

        self.root = root
        fd_path = os.path.join(self.root, "$FD")

        if not os.path.isdir(root):
            raise OSError("Root of file descriptor isn't a valid file or folder")
        
        if os.path.isfile(fd_path) and os.path.getsize(fd_path)!=0:
            self.file = open(fd_path, "r+")
            
            try:
                self.files = json.load(self.file)
            except:
                raise OSError("Failed to parse the filedescriptor from json, file descriptor corrupted")
        else:
            self.file = open(fd_path, "w") # TODO: Error handling
            self.files = {}
            self.files["metadata"] = {}
            self.files["metadata"]["last_id"] = "0"

        self.metadata = self.files["metadata"]
            
    def __get_last_id(self):
        return self.metadata["last_id"]

    def __inc_last_id(self):
        self.metadata["last_id"] = str(int(self.metadata["last_id"]) + 1)
        return self.metadata["last_id"]

    def __del__(self):
        self.file.close()

    def add_file(self, name, path, encryption_alg_sig, splitting_alg_sig, clouds_order):
        """
        Add a new file to the filedescriptor listing
        @return the file_id
        """
        # TODO: check if data is valid
        new_id = self.__inc_last_id()
        now = str(datetime.now(timezone.utc).timestamp())

        # split = file_path.split("/")
        # name = split[-1]
        # path = "/".join(split[:-1])

        self.files[new_id] = {
            "name": name,
            "path": path,
            "upload_date" : now,
            "edit_date" : now,
            "e_alg" : encryption_alg_sig,
            "s_alg" : splitting_alg_sig,
            "parts" : clouds_order
        }
        return new_id

    def delete_file(self, file_id):
        """
        Delete a file listing for a file that does not exist anymore
        @return the file metadata that got deleted
        """
        return self.files.pop(file_id)

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
        Returns the list of all files in the FileDescriptor as follows:
        [
            [file_id, name, path, upload_date, edit_date],
            [file_id, name, path, upload_date, edit_date],
            ...
        ]
        """
        return [{"id": id, "name": f["name"], "path": f["path"], "upload_date": f["upload_date"], "edit_date": f["edit_date"]} for id,f in self.files.items() if id!="metadata"]

    
    def sync_to_file(self):
        """
        Sync the filemapping to disk
        """
        self.file.seek(0)
        self.file.truncate()
        json.dump(self.files, self.file)

    def __str__(self):
        return str(self.files)
