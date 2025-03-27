import os
import json
from datetime import datetime, timezone

"""
File descriptors look like this:
FD:
{
    metadata = {
        last_id, the last id in the descriptor
        enc_sig, the encryption algorithm signature for the session
        split_sig, the splitting algorithm signature for the session
    }
    id = {
        name, The name of the file
        path, The path of the file in EncryptoSphere
        upload_date, The upload date
        edit_date, The edit date
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

    def __init__(self, data : bytes | None, metadata : bytes | None, encrypt_sig=None, split_sig=None):
        """
        Creates a new FileDescriptor object from an existing FileDescriptor file
        Creating a filedescriptor with an invalid filedescriptor file will raise an OSError
        @param data the data for the already existing FD or None
        """
        self.files_ready = False
        if not data and not metadata:
            self.files = {}
            self.metadata = {}
            self.metadata["last_id"] = "0"
            self.metadata["enc_sig"] = encrypt_sig
            self.metadata["split_sig"] = split_sig
            self.files_ready = True
        else:
            try:
                self.metadata = self.deserialize(metadata)
            except:
                raise OSError("Failed to parse the filedescriptor from json, file descriptor metadata corrupted")
            if data:
                self.set_files(data)
                self.files_ready = True

    def set_files(self, data):
        """
        Deserializes data and sets it as the files list
        """
        try:
            self.files = self.deserialize(data)
        except:
            raise OSError("Failed to parse the filedescriptor from json, file descriptor corrupted")

    def __get_last_id(self):
        return self.metadata["last_id"]

    def __inc_last_id(self):
        self.metadata["last_id"] = str(int(self.metadata["last_id"]) + 1)
        return self.metadata["last_id"]
    
    def get_encryption_signature(self):
        return self.metadata["enc_sig"]
    
    def get_split_signature(self):
        return self.metadata["split_sig"]

    def add_file(self, name, path, clouds_order, hash, file_id=None):
        """
        Add a new file to the filedescriptor listing
        @return the file_id
        """
        # TODO: check if data is valid
        if file_id is not None and file_id in self.files:
            raise ValueError(f"File ID {file_id} is already in use.")

        # If no file_id provided, generate a new one
        if file_id is None:
            new_id = self.__inc_last_id()
        else:
            new_id = file_id
        now = str(datetime.now(timezone.utc).timestamp())

        # split = file_path.split("/")
        # name = split[-1]
        # path = "/".join(split[:-1])

        self.files[new_id] = {
            "name": name,
            "path": path,
            "upload_date" : now,
            "edit_date" : now,
            "parts" : clouds_order,
            "hash": hash
        }
        return new_id
    
    def get_next_id(self):
        """
        returns the next id that will be used for a file
        updates the last_id in the metadata
        """
        return self.__inc_last_id() 
    
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
        return [{"id": id, "name": f["name"], "path": f["path"], "upload_date": f["upload_date"], "edit_date": f["edit_date"]} for id,f in self.files.items()]

    def serialize(self):
        """
        Serializes the data and metadata
        @return data,metadata serialized
        """
        if not self.files_ready:
            raise Exception("Files are not available, use set_files")
        return json.dumps(self.files).encode('utf-8'), json.dumps(self.metadata).encode('utf-8')
    
    def deserialize(self, data):
        """
        Deserializes data and metadata
        """
        return json.loads(data)

    def __str__(self):
        return str(self.metadata) + "\r\n" + str(self.files)
    
    def get_files_in_folder(self, folder_name):
        """
        Returns a recursive list of all the entrees for files in a specific folder based on their path 
        """
        file_list = []
        for id,file in self.files.items():
            if file["path"].startswith(folder_name):
                file_list.append(file)
        
        return file_list
