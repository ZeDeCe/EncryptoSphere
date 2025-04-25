import os
import tempfile
import hashlib

from modules import Split
from modules import Encrypt
from modules.CloudAPI import CloudService
import json
from CloudObjects import Directory, CloudFile

import concurrent.futures
import time
import threading

SYNC_TIME = 300  # Sync time in seconds
FILE_DESCRIPTOR_FOLDER = os.path.join(os.getcwd(), "Test") #temporary
FILE_INDEX_SEPERATOR = "#"

class CloudManager:
    """
    This class is the top application layer for handling actions that relate to files from OS to cloud services
    CloudManager does not handle errors and throws any error to user classes to handle.
    """
    def __init__(self, clouds : list[CloudService], root : str, split : Split, encrypt : Encrypt):
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
        self.cloud_name_list = list(map(lambda c: c.get_name(), self.clouds))
        self.fd = None
        self.sync_thread = None
        self.stop_event = threading.Event()  # Event to signal
        self.fs : dict[str, CloudFile | Directory]= {} # filesystem
        self.username = "main_session" # Temporary until login module
        #self.lock_session()
        self.executor = concurrent.futures.ThreadPoolExecutor()

    def __del__(self):
        self.executor.shutdown(wait=True)

    def _complete_cloud_threads(self, futures: dict[concurrent.futures.Future, str]) -> tuple[list[tuple[any, any]], bool]:
        """
        Waits for all threads to finish and returns the results
        @param futures a dictionary of futures and their corresponding cloud objects/names {future: cloud, ...}
        @return a tuple containing: (a list of tuples (value, result), success)
        """
        results = []
        success = True
        for future in concurrent.futures.as_completed(futures):
            cloud_name = futures[future]
            try:
                result = future.result()
                results.append((cloud_name, result))
                print(f"Successfully executed task for cloud {cloud_name}.")
            except Exception as e:
                success = False
                results.append((cloud_name, e))
                print(f"Error executing task to {cloud_name}: {e}")
        return results, success

    def lock_session(self):
        """
        Checks if a session file is active on the cloud
        If it is raise error.
        If not then place one to lock the session
        """
        for cloud in self.clouds:
            session_file_name = f"SESSION_ACTIVE_{cloud.get_email()}"
            try:
                # Check if the session file already exists
                existing_file = cloud.download_file(session_file_name, self.root_folder)
                if existing_file is not None:
                    print(f"Session is already active for user {cloud.get_email()} on cloud {cloud.get_name()}.")
                    raise Exception(f"Session is already active for user {cloud.get_email()} on cloud {cloud.get_name()}.")

                # Create the session file
                cloud.upload_file(b"SESSION ACTIVE", session_file_name, self.root_folder)
                print(f"Session locked for user {cloud.get_email()} on cloud {cloud.get_name()}.")
            except Exception as e:
                print(f"Error locking session for cloud {cloud.get_name()}: {e}")
                raise
    
    def unlock_session(self):
        """
        Removes the "SESSION ACTIVE" file from the root directory of each cloud to unlock the session.
        """
        for cloud in self.clouds:
            session_file_name = f"SESSION_ACTIVE_{cloud.get_email()}"
            try:
                # Delete the session file
                cloud.delete_file(session_file_name, self.root_folder)
                print(f"Session unlocked for user {cloud.get_email()} on cloud {cloud.get_name()}.")
            except Exception as e:
                print(f"Error unlocking session for cloud {cloud.get_name()}: {e}")
                raise

    def _split(self, data : bytes, clouds : int):
        return self.split.split(data, clouds)
    
    def _merge(self, data: list[bytes], clouds: int):
        # TODO: finish function
        return self.split.merge_parts(data, clouds)
    
    def _encrypt(self, data: bytes) -> bytes:
        """
        Encrypts the data using the encryption method provided.
        Raises an exception if encryption fails.
        """
        if data is None:
            raise ValueError("Cannot encrypt: data is None.")
        return self.encrypt.encrypt(data)
    
    def _decrypt(self, data: bytes) -> bytes:
        """
        Decrypts the data using the encryption method provided.
        Raises an exception if decryption fails.
        """
        if data is None:
            raise ValueError("Cannot decrypt: data is None.")
        if data.endswith(b'\x00'):
            data = data.rstrip(b'\x00')
        return self.encrypt.decrypt(data)

    def _tempfile_from_path(self, os_filepath):
        file = tempfile.TemporaryFile(dir=os.path.dirname(os_filepath))
        with open(os_filepath, "r") as osfile:
            file.write(osfile.read().encode('utf-8'))
        return file
    
    def _get_directory(self, path : str) -> Directory:
        """
        Function to traverse a directory and return the object
        """
        # Check if we have it cached
        if path in self.fs and isinstance(self.fs.get(path), Directory):
            return self.fs[path]
        
        # Go through all folders in cache that match path and try to find one of them
        parent = '/'.join(path.rstrip('/').split('/')[:-1]) or '/'
        while True:
            if parent in self.fs and isinstance(self.fs.get(parent), Directory):
                parent = self.fs.get(parent)
                break
            path = '/'.join(path.rstrip('/').split('/')[:-1]) or '/'

        # Create each folder
        futures = {}
        current_path = parent.path
        for name in path.split("/")[len(parent.path.split("/")):]:
            current_path = f"{current_path}/{name}"
            for cloud in self.clouds:
                futures[self.executor.submit(cloud.create_folder, name, parent.get(cloud.get_name()))] = cloud.get_name()
            results, success = self._complete_cloud_threads(futures)
            if not success:
                raise Exception(f"Cannot create folder at path {current_path}")
            folders = {}
            for tupl in results:
                folders[tupl[0]] = tupl[1]
            parent = Directory(folders, path=current_path)
            self.fs[current_path] = parent

    def authenticate(self):
        """
        Authenticates the clouds and loads the file descriptor.
        Returns True if the process succeeds, False otherwise.
        """
        futures = {}
        folders = {}
        
        # Authenticate all clouds
        for cloud in self.clouds:
            try:
                cloud.authenticate_cloud()
                futures[self.executor.submit(cloud.get_session_folder, self.username)] = cloud.get_name()
            except Exception as e:
                print(f"Error during cloud authentication: {e}")
                return False
            
        # Get root folders
        for future in concurrent.futures.as_completed(futures):
            cloud_name = futures[future]
            try:
                result = future.result()
                folders[cloud_name] = result
                print(f"Successfully found session folder for cloud {cloud_name}.")
            except Exception as e:
                print(f"Failed to get session folder in cloud: {e}")
                return False
        try:
            # Attempt to load the file descriptor
            
            self.fs["/"] = Directory(folders, "/")
            self.fs["/"].set_root()
            self.load_metadata()

            return True  # Authentication and file descriptor loading succeeded
        except Exception as e:
            print(f"Error during authentication, loading of file descriptor: {e}")
            return False
        
    def upload_file(self, os_filepath, path="/", sync=True):
        """
        Uploads a single file to the cloud.
        
        @param os_filepath: The path to the file on the OS.
        @param path: The root path for the file in EncryptoSphere hierarchy.
        @param sync: Whether to sync the file descriptor after uploading. Defaults to True.
        """
        if not os.path.isfile(os_filepath):
            raise OSError()
        
        filebasename = os.path.basename(os_filepath)
        filepath = f"{path if path != '/' else ''}/{filebasename}"
        if filepath in self.fs:
            raise Exception(f"File or folder already exists with given path {path}")
        
        data = None
        with open(os_filepath, 'rb') as file:
            data = file.read()
        data = self._encrypt(data)
        data = self._split(data, len(self.clouds))

        # Upload file parts to clouds
        futures = {}
        for cloud_index, f in enumerate(data):
            cloud = self.clouds[cloud_index]
            for file_index, file_content in enumerate(f):
                file_name = f"{file_index+1}{FILE_INDEX_SEPERATOR}{filebasename}"
                futures[self.executor.submit(cloud.upload_file, file_content, file_name, self._get_directory(path).get(cloud.get_name()))] = cloud
        results, success = self._complete_cloud_threads(futures)
        if not success:
            pass # TODO: one part didn't load correctly, check if this is fine according to our split

        parts = {}
        # Ensure the clouds are in correct order
        for cloud in self.clouds:
            parts[cloud] = []

        # Get results in the parts dict
        for (cloud, file) in results:
            parts[cloud].append(file)
        self.fs[filepath] = CloudFile(parts, filepath)

        return self.fs[filepath].get_data()
    
     
    def _upload_replicated(self, file_name, data, suffix=False):
        """
        Uploads the given file to all platforms without splitting.
        This function is purposefully limited to only uploading from the root folder
        @param file_name the name of the file on the cloud
        @param data the data to be written
        @param suffix, optional if True will add the email of the user to the file name at the end
        """
        futures = {}
        for cloud in self.clouds:
            print(f"Uploading to {cloud.get_name()}")
            suffix = f"_{cloud.get_email()}" if suffix else ""
            futures[self.executor.submit(cloud.upload_file, data, f"{file_name}{suffix}", self.fs["/"].get(cloud.get_name()))] = cloud.get_name()
        results, success = self._complete_cloud_threads(futures)
        if not success:
            raise Exception("Failed to upload replicated file to all clouds.")
        return True

    def _download_replicated(self, file_name, suffix=False):
        """
        Downloads and decrypts a the file from the path given if it exists in at least one of the clouds
        This function is purposefully limited to only downloading from the root folder
        @return the data of the file if succeeded, None otherwise
        """
        for cloud in self.clouds:
            suffix = f"_{cloud.get_email()}" if suffix else ""
            try:
                meta = cloud.list_files(self.fs["/"].get(cloud.get_name()), file_name)
                found = None
                for data in meta:
                    if data.get_name() == file_name:
                        found = data
                        break
                if found is None:
                    raise Exception("Cannot find file in cloud")
                file_data = cloud.download_file(found)
                if file_data is not None:
                    print(f"Successfully downloaded {file_name}{suffix} from {cloud.get_name()}.")
                    return file_data  # Return the data if download is successful
            except Exception as e:
                print(f"Failed to download {file_name}{suffix} from {cloud.get_name()}: {e}")
                continue  # Move to the next cloud if the current one fails

        return None  # Return None if all clouds fail
    
    def _delete_replicated(self, file_name, suffix=False):
        for cloud in self.clouds:
            suffix = f"_{cloud.get_email()}" if suffix else ""
            file = cloud.list_files(self.fs["/"].get(cloud.get_name()), file_name) # This is running sync, might be a problem
            for data in file:
                if data.get_name() == file_name:
                    file = data
                    break
            self.executor.submit(cloud.delete_file, file)
        # we don't even wait for the results
    
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
        This function uploads an entire folder to the cloud.
        Synchronization is deferred until all files are uploaded.
        
        @param os_folder: The folder path on the OS to upload.
        @param path: The root path for the folder in EncryptoSphere hierarchy.
        """
        os_folder = os.path.abspath(os_folder)
        folder_name = os.path.basename(os_folder)
        if path[-1] != "/":
            path = f"{path}/"
        
        # Iterate over the folder and upload each file
        futures = {}
        for root, _, files in os.walk(os_folder):
            root_arr = root.split(os.sep)
            root_arr = root_arr[root_arr.index(folder_name):]
            encrypto_root = "/".join(root_arr)
            for file in files:
                futures[self.executor.submit(self.upload_file, os.path.join(root, file), f"{path}{encrypto_root}", False)] = None
        results, success = self._complete_cloud_threads(futures)
        if not success:
            raise Exception("Failed to upload folder contents to clouds.")
        
        # Sync file descriptor once after all uploads
        self.sync_fd()
        return True

    def download_file(self, path):
        """
        Downloads a file from the various clouds
        file_id is a FileDescriptor ID of the file.
        Make sure to check if the clouds of this object exist in the "parts" array
        """
        try:
            
            file : CloudFile = self.fs[path]
            if not file:
                raise Exception("Looking for file that does not exist! Try running get_items_in_folder")
            futures = {}
            current_index = 0
            
            for cloud, parts in file.parts.items():
                cloud_name = cloud.get_name()
                for part in parts:
                    futures[self.executor.submit(cloud.download_file, part)] = (cloud_name, current_index)
                    current_index += 1
            results, success = self._complete_cloud_threads(futures)

            data = [None] * current_index

            # Iterate over the results and place them in the correct order
            valid_parts = 0
            for (cloud_name, index), result in results:
                if isinstance(result, bytes):
                    # Use the index from the metadata to place the part in the correct position
                    data[index] = result
                    valid_parts += 1
            
            if valid_parts < self.split.min_parts:
                raise ValueError(f"Insufficient valid parts for file {path}. Valid parts: {valid_parts}/{len(data)}")

            # Merge and decrypt the data
            if not data:
                raise ValueError(f"No data downloaded for file {path}.")
            try:
                encrypted_data = self._merge(data, len(self.clouds))
                data = self._decrypt(encrypted_data)
            except Exception as e:
                print(f"Error merging or decrypting data for file {path}: {e}")
                raise

            # Set the destination path to the Downloads folder
            downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
            dest_path = os.path.join(downloads_folder, file.data.get("name"))

            # Write the reconstructed file to the destination path
            try:
                with open(dest_path, 'wb') as output:
                    output.write(data)
                print(f"File successfully reconstructed into '{dest_path}'.")
            except Exception as e:
                print(f"Error writing file to {dest_path}: {e}")
                raise

            return True

        except ValueError as ve:
            print(f"ValueError: {ve}")
        except FileNotFoundError as fnfe:
            print(f"FileNotFoundError: {fnfe}")
        except Exception as e:
            print(f"Unexpected error while downloading file: {e}")
        return False

    def download_folder(self, folder_name):
        """
        Using filedescriptor functions, gathers all files under the folder_name and then calls self.download
        on all of those files. Constructs them as the hierarchy in the filedescriptor on the OS.
        """

    def delete_file(self, file_id):
        """
        Deletes a specific file from file ID using the filedescriptor
        @param file_id the file id to delete
        """
        file_data = self.fd.get_file_data(file_id)
        parts = file_data['parts']
        futures = {}
        for cloud_name, part_count in parts.items():
            cloud = next((cloud for cloud in self.clouds if cloud.get_name() == cloud_name), None)
            if cloud is None:
                raise ValueError(f"Cloud {cloud_name} not found in the current session.")    
            for part_number in range(1, part_count + 1): 
                futures[self.executor.submit(cloud.delete_file, f"{file_id}_{part_number}", self.root_folder)] = cloud_name
        results, success = self._complete_cloud_threads(futures)
        if not success:
            raise Exception("Failed to delete file parts from clouds.")
        
        self.fd.delete_file(file_id)
        self.sync_fd()
        return True

    def delete_folder(self, folder_path):
        """
        Given a path in EncryptoSphere (/EncryptoSphere/...), deletes all files with that path name
        @param folder_path the path to the folder in the file descriptor
        """
        return True
    
    def get_items_in_folder(self, path):
        folder = self.fs.get(path)
        if not folder:
            raise FileNotFoundError(f"Folder with path {path} does not exist!")
        
        for item_path, item in self.fs.items():
            if item_path == '/':
                continue
            mydir = "/".join(item_path.split("/")[:-1])
            mydir = mydir if mydir != '' else '/'
            if mydir == path:
                yield item.get_data()
        
        files = {}
        folders = {}
        for cloud in self.clouds:
            for result in cloud.get_children(folder.get(cloud.get_name()), filter="$"):
                
                if isinstance(result, CloudService.File):
                    split = result.name.split(FILE_INDEX_SEPERATOR)
                    actual_path = f"{folder.path if folder.path != '/' else ''}/{split[-1]}"
                    if not files.get(actual_path):
                        files[actual_path] = {}
                    if not files.get(actual_path).get(cloud):
                        files.get(actual_path)[cloud] = [None] * self.split.copies_per_cloud
                    index = split[0] if len(split) == 2 else 1
                    try:
                        index = int(index) -1
                    except:
                        raise Exception("File has a special character in the name")
                    files.get(actual_path).get(cloud)[index] = result

                elif isinstance(result, CloudService.Folder):
                    actual_path = f"{folder.path if folder.path != '/' else ''}/{result.name}"
                    cloud_name = cloud.get_name()
                    if not folders.get(actual_path):
                        folders[actual_path] = {}
                    folders.get(actual_path)[cloud_name] = result
                else:
                    print("Invalid type found - danger")
                    continue

        for folder_path, f in folders.items():
            dir = Directory(f, folder_path)
            if not self.fs.get(folder_path):
                yield dir.get_data()
            self.fs[folder_path] = dir
            
        for file_path, parts in files.items():
            f = CloudFile(parts, file_path)
            if not self.fs.get(file_path):
                yield f.get_data()
            self.fs[file_path] = f
        
        
                
    def load_metadata(self):
        """
        Downloads the filedescriptor from the clouds, decrypts it using self.decrypt, and sets it as this object's file descriptor
        """
        metadata = self._download_replicated("$META")
        if metadata is None: # Metadata does not exist, new session, make our own
            self.metadata = {"encrypt": self.encrypt.get_name(), "split": self.split.get_name(), "order": self.cloud_name_list}
            self._upload_replicated("$META", json.dumps(self.metadata).encode('utf-8'))
        else:
            self.metadata = json.loads(metadata)
            for cloudname in self.metadata.get("order"):
                if not cloudname in self.cloud_name_list: # TODO: Make it so only the needed amount of clouds are checked
                    raise Exception(f"Missing a required cloud for session: {cloudname}")
            if self.split.get_name() != self.metadata.get("split"):
                raise Exception("Bad splitting algorithm chosen for session")
            if self.encrypt.get_name() != self.metadata.get("encrypt"):
                raise Exception("Bad encryption algorithm chosen for session")


