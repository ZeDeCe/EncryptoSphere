import os
import tempfile
import hashlib

from modules import Split
from modules import Encrypt
from modules.CloudAPI import CloudService
import FileDescriptor

import concurrent.futures
import time
import threading

SYNC_TIME = 300  # Sync time in seconds
FILE_DESCRIPTOR_FOLDER = os.path.join(os.getcwd(), "Test") #temporary

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
        mainroot = os.getenv("ENCRYPTO_ROOT")
        self.root_folder = f"{mainroot}{root}"
        self.cloud_name_list = list(map(lambda c: c.get_name(), self.clouds))
        self.fd = None
        #file_descriptor if file_descriptor else self.sync_from_clouds()
        self.sync_thread = None
        self.stop_event = threading.Event()  # Event to signal
        self.lock_session()
        self.executor = concurrent.futures.ThreadPoolExecutor()

    def __del__(self):
        self.executor.shutdown(wait=True)

    def _complete_cloud_threads(self, futures: dict[concurrent.futures.Future, str]):
        """
        Waits for all threads to finish and returns the results
        @param futures a dictionary of futures and their corresponding cloud names {future: cloud_name, ...}
        @return a tuple containing: (success, a list of tuples (cloud_name, result))
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
        pass

    def _split(self, data : bytes, clouds : int):
        return self.split.split(data, clouds)
    
    def _merge(self, data: list[bytes], clouds: int):
        # TODO: finish function
        return self.split.merge_parts(data, clouds)
    
    def _encrypt(self, data : bytes):
        data = self.encrypt.encrypt(data)
        return data
    
    def _decrypt(self, data : bytes):
        if data.endswith(b'\x00'):
            data = data.rstrip(b'\x00')  # Remove only the null byte at the end
        clear_data = self.encrypt.decrypt(data)
        return clear_data

    def _tempfile_from_path(self, os_filepath):
        file = tempfile.TemporaryFile(dir=os.path.dirname(os_filepath))
        with open(os_filepath, "r") as osfile:
            file.write(osfile.read().encode('utf-8'))
        return file

    def authenticate(self):
        """
        Authenticates the clouds and loads the file descriptor.
        Returns True if the process succeeds, False otherwise.
        """
        try:
            # Authenticate all clouds
            for cloud in self.clouds:
                cloud.authenticate_cloud()

            # Attempt to load the file descriptor
            fd_loaded = self.load_fd()
            if not fd_loaded:
                print("Failed to load file descriptor.")
                return False

            # Start the sync thread if not already running
            if not self.sync_thread or not self.sync_thread.is_alive():
                self.start_sync_thread()

            return True  # Authentication and file descriptor loading succeeded

        except Exception as e:
            print(f"Error during authentication: {e}")
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
        
        data = None
        with open(os_filepath, 'rb') as file:
            data = file.read()
        hash = hashlib.md5(data).hexdigest()
        data = self._encrypt(data)
        data = self._split(data, len(self.clouds))

        file_id = self.fd.get_next_id()
        cloud_file_count = {}

        # Upload file parts to clouds
        futures = {}
        for cloud_index, f in enumerate(data):
            cloud_name = self.clouds[cloud_index].get_name()
            cloud_file_count[cloud_name] = len(f)
            for file_index, file_content in enumerate(f):
                file_name = f"{file_id}_{file_index+1}"
                futures[self.executor.submit(self.clouds[cloud_index].upload_file, file_content, file_name, self.root_folder)] = cloud_name
     
        results, success = self._complete_cloud_threads(futures)
        if not success:
            raise Exception("Failed to upload file parts to clouds.")
        
        # Add file metadata to the file descriptor
        file_id = self.fd.add_file(
            os.path.basename(os_filepath),
            path,
            cloud_file_count,
            hash,
            file_id
        )
        
        # Sync file descriptor if requested
        if sync:
            self.sync_fd()
        
        return self.fd.get_file_data(file_id)
    
            
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
            futures[self.executor.submit(cloud.upload_file, data, f"{file_name}{suffix}", self.root_folder)] = cloud.get_name()
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
                file_data = cloud.download_file(f"{file_name}{suffix}", self.root_folder)
                if file_data is not None:
                    print(f"Successfully downloaded {file_name}{suffix} from {cloud.get_name()}.")
                    return file_data  # Return the data if download is successful
            except Exception as e:
                print(f"Failed to download {file_name}{suffix} from {cloud.get_name()}: {e}")
                continue  # Move to the next cloud if the current one fails

        return None  # Return None if all clouds fail
    
    def _delete_replicated(self, file_name, suffix=False):
        futures = {}
        for cloud in self.clouds:
            suffix = f"_{cloud.get_email()}" if suffix else ""
            self.executor.submit(cloud.delete_file, f"{file_name}{suffix}", self.root_folder)
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

    def download_file(self, file_id):
        """
        Downloads a file from the various clouds
        file_id is a FileDescriptor ID of the file.
        Make sure to check if the clouds of this object exist in the "parts" array
        """
        try:
            file_data = self.fd.get_file_data(file_id)
            if not file_data:
                raise ValueError(f"File descriptor for file_id {file_id} not found.")

            parts = file_data.get('parts', {})
            if not parts:
                raise ValueError(f"No parts found for file_id {file_id} in the file descriptor.")

            data = []
            futures = {}
            # Iterate over clouds and download file parts
            for cloud_name, part_count in parts.items():
                cloud = next((cloud for cloud in self.clouds if cloud.get_name() == cloud_name), None)
                if cloud is None:
                    raise ValueError(f"Cloud {cloud_name} not found in the current session.")
                for part_number in range(1, part_count + 1):
                    file_name = f"{file_id}_{part_number}"
                    if cloud is None:
                        raise ValueError(f"Cloud {cloud_name} not found in the current session.")
                    futures[self.executor.submit(cloud.download_file, file_name, self.root_folder)] = cloud_name
                    
            # Wait for all download threads to complete
            results, success = self._complete_cloud_threads(futures)
            if not success:
                raise FileNotFoundError(f"File part {file_name} not found in {cloud_name}.")
            
            data = [res[1] for res in results if isinstance(res[1], bytes)]

            # Merge and decrypt the data
            if not data:
                raise ValueError(f"No data downloaded for file_id {file_id}.")
            try:
                encrypted_data = self._merge(data, len(self.clouds))
                file = self._decrypt(encrypted_data)
            except Exception as e:
                print(f"Error merging or decrypting data for file_id {file_id}: {e}")
                raise

            # Get the file metadata and filename
            file_name = file_data.get("name")
            if not file_name:
                raise ValueError(f"Filename not found in file descriptor for file_id {file_id}.")

            # Set the destination path to the Downloads folder
            downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
            dest_path = os.path.join(downloads_folder, file_name)

            # Write the reconstructed file to the destination path
            try:
                with open(dest_path, 'wb') as output:
                    output.write(file)
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
        self.sync_fd()
        return True

    def get_file_list(self):
        return self.fd.get_file_list()
    
    def get_items_in_folder(self, path):
        return self.fd.get_items_in_folder(path)

    def sync_to_clouds(self):
        """
        Uploads the filedescriptor to the clouds encrypted using self.encrypt
        This function should use upload_replicated
        """
        data, metadata = self.fd.serialize()
        if metadata:
            self.executor.submit(self._upload_replicated, "$FD_META", metadata)
        if data:
            self.executor.submit(self._upload_replicated, "$FD", self._encrypt(data))
        print("FDs Synced to clouds")

    def start_sync_thread(self):
        """
        Starts a background thread to run sync_to_clouds every 5 minutes.
        """
        def sync_task():
            while not self.stop_event.is_set():  # Check if stop_event is set
                #self.sync_to_clouds()
                time.sleep(SYNC_TIME)  

        # Start the sync task in a separate thread
        self.sync_thread = threading.Thread(target=sync_task, daemon=True)
        self.sync_thread.start()
    
    def stop_sync_thread(self):
        """
        Stops the background sync thread.
        """
        if self.sync_thread and self.sync_thread.is_alive():
            self.stop_event.set()  # Signal the thread to stop

    def load_fd(self):
        """
        Downloads the filedescriptor from the clouds, decrypts it using self.decrypt, and sets it as this object's file descriptor
        """
        data = self._download_replicated("$FD")
        metadata = self._download_replicated("$FD_META")
        # Technically supposed to pull encryption decryption from cloud or at least check it matches
        # TODO: Check here if a version is still in desktop, means corruption
        self.fd = FileDescriptor.FileDescriptor(None if data == None else self._decrypt(data), metadata, self.encrypt.get_name(), self.split.get_name())
        return True
    
    def sync_fd(self):
        """
        Syncs the file descriptor
        This function is called after every operation
        """
        fd_file_path = os.path.join(".", "Test") #temporary
        try:
            if not os.path.exists(fd_file_path):
                os.makedirs(fd_file_path)
        except:
            raise OSError("Root folder given for FD is invalid")
        data = None
        metadata = None
        try:
            data, metadata = self.fd.serialize()
        except:
            raise Exception("Failed to serialize fd")

        try:
            with open(os.path.join(fd_file_path, "$FD"), "wb") as f:
                f.write(self._encrypt(data)) 
            with open(os.path.join(fd_file_path, "$FD_META"), "wb") as f:
                f.write(metadata)
        except:
            print("Failed to write to {fd_file_path}")
        
    def delete_fd(self):
        """
        Deletes the file descriptor file from disk
        This function should be used to clean up the file descriptor file after the session is over
        """
        try:
            os.remove(os.path.join(FILE_DESCRIPTOR_FOLDER, "$FD"))
            os.remove(os.path.join(FILE_DESCRIPTOR_FOLDER, "$FD_META"))
            print("$FD deleted successfully!")
        except FileNotFoundError:
            print("File not found.")
        except PermissionError:
            print("You do not have permission to delete the file.")
        except Exception as e:
            print(f"Error: {e}")


