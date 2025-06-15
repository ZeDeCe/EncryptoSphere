import os
import tempfile
import shutil


from modules import Split
from modules import Encrypt
from modules.CloudAPI import CloudService
import json
from CloudObjects import Directory, CloudFile


import concurrent.futures
import threading


SYNC_TIME = 300  # Sync time in seconds
FILE_DESCRIPTOR_FOLDER = os.path.join(os.getcwd(), "Test") #temporary
FILE_INDEX_SEPERATOR = "#"
SHARED_TEMP_FOLDER = None

class CloudManager:
    """
    This class is the top application layer for handling actions that relate to files from OS to cloud services
    CloudManager does not handle errors and throws any error to user classes to handle.
    """
    def __init__(self, clouds : list[CloudService], root : str, split : Split, encrypt : Encrypt):
        """
        Initialize a cloudmanager and a session
        @param clouds the cloud classes to use
        @param root the root directory name
        @param split the split class to use
        @param encrypt the encrypt class to use
        @param file_descriptor the filedescriptor to use. If none provided, will assume that the session already exists and try syncing it from the cloud
        """
        self.split = split
        self.encrypt = encrypt
        self.clouds = clouds
        self.cloud_name_list = list(map(lambda c: c.get_name(), self.clouds))
        self.fd = None
        self.sync_thread = None
        self.temporary_files = []
        self.dup_lock = threading.RLock()
        self.stop_event = threading.Event()  # Event to signal
        self.fs : dict[str, CloudFile | Directory]= {} # filesystem
        self.root = root # Temporary until login module
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(self.clouds) * 5)
        self.initialize_temp_folder()


    def __del__(self):
        try:
            self.executor.shutdown(wait=True)
        except RuntimeError as e:
            print(f"Error shutting down executor: {e}")

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
    
    def _get_directory(self, path : str) -> Directory:
        """
        Function to traverse a directory and return the object
        """
        # Check if we have it cached
        if path in self.fs and isinstance(self.fs.get(path), Directory):
            return self.fs.get(path)
        
        # Go through all folders in cache that match path and try to find one of them
        parent = '/'.join(path.rstrip('/').split('/')[:-1]) or '/'
        while not (parent in self.fs and isinstance(self.fs.get(parent), Directory)):
            if parent == '/':
                print("We somehow do not have the root folder loaded (/). Running authenticate")
                self.authenticate()
            parent = '/'.join(parent.rstrip('/').split('/')[:-1]) or '/'
        parent = self.fs.get(parent)
        # Create each folder
        futures = {}
        current_path = parent.path if parent.path != "/" else ""
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
        return self.fs[path]

    def initialize_temp_folder(self):
        """
        Create a shared temporary folder for the application.
        """
        global SHARED_TEMP_FOLDER
        if SHARED_TEMP_FOLDER is None:
            SHARED_TEMP_FOLDER = tempfile.mkdtemp(prefix="EncryptoSphere_")
            print(f"Shared temporary folder created: {SHARED_TEMP_FOLDER}")

    def cleanup_temp_folder(self):
        """
        Delete the shared temporary folder and its contents.
        """
        global SHARED_TEMP_FOLDER
        if SHARED_TEMP_FOLDER and os.path.exists(SHARED_TEMP_FOLDER):
            shutil.rmtree(SHARED_TEMP_FOLDER)
            print(f"Shared temporary folder deleted: {SHARED_TEMP_FOLDER}")
            SHARED_TEMP_FOLDER = None

    def get_temp_file_path(self, filename=None):
        """
        Get the full path to a file in the shared temporary folder.
        """
        if not SHARED_TEMP_FOLDER:
            raise Exception("Shared temporary folder is not initialized.")
        if filename is None:
            return SHARED_TEMP_FOLDER
        else:
            return os.path.join(SHARED_TEMP_FOLDER, filename)
        
    def check_for_duplicates(self, path):
        with self.dup_lock:
            return path in self.temporary_files
        
    def create_temporary_placeholder(self, path):
        if self.check_for_duplicates(path):
            return None
        with self.dup_lock:
            self.temporary_files.append(path)
            return path
    
    def remove_temporary_placeholder(self, path):
        if not self.check_for_duplicates(path):
            return
        with self.dup_lock:
            self.temporary_files.remove(path)

    def authenticate(self):
        """
        Authenticates the clouds and loads the file descriptor.
        Returns True if the process succeeds, False otherwise.
        """
        futures = {}
        folders = {}
        if not self.clouds[0].is_authenticated():
            raise Exception("Clouds are not authenticated. Please authenticate at least one before proceeding.")
        
        self.load_metadata()

        # Authenticate all clouds
        for cloud in self.clouds:
            try:
                cloud.authenticate_cloud()
                futures[self.executor.submit(cloud.get_session_folder, self.root)] = cloud.get_name()
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
            

            return True  # Authentication and file descriptor loading succeeded
        except Exception as e:
            print(f"Error during authentication, loading of file descriptor: {e}")
            return False
        
    def upload_file(self, os_filepath, path="/", name=None):
        """
        Uploads a single file to the cloud.
        
        @param os_filepath: The path to the file on the OS.
        @param path: The root path for the file in EncryptoSphere hierarchy.
        @param sync: Whether to sync the file descriptor after uploading. Defaults to True.
        """

        if not os.path.isfile(os_filepath):
            raise Exception(f"File not found")
        if name:
            filebasename = name
        else:
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
            files = cloud.list_files(self.fs["/"].get(cloud.get_name()), f"{file_name}{suffix}")
            file : CloudService.File = None
            for f in files:
                if f.get_name() == f"{file_name}{suffix}":
                    file = f
                    break
            if file is None:
                print(f"Failed to find replicated file {file_name}{suffix}")
                return False
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
    
    def create_folder(self, path : str) -> bool:
        """
        Creates a new folder in the encryptosphere filesystem
        @param path the path to create the folder in
        @return success
        """
        if not self.fs.get(path) is None:
            return True
        
        parent_path = "/".join(path.split("/")[:-1])
        parent_path = "/" if parent_path == "" else parent_path
        parent = self._get_directory(parent_path)
        name = path.split("/")[-1]
        if name == "":
            raise Exception("Cannot create root folder using create_folder!")
        futures = {}
        for cloud in self.clouds:
            futures[self.executor.submit(cloud.create_folder, name, parent.get(cloud.get_name()))] = cloud
        results, success = self._complete_cloud_threads(futures)
        if not success:
            raise Exception("Failed to create folder in some clouds")
        folders = {}
        for cloud,folder in results:
            folders[cloud.get_name()] = folder
        self.fs[path] = Directory(folders, path)
        return True

    def upload_folder(self, os_folder, path):
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
        
        # First upload main folder
        self.create_folder(f"{path}{folder_name}")

        file_amount = 0
        # Create all subdirectories
        with concurrent.futures.ThreadPoolExecutor() as folder_executor:
            for root, dirs, files in os.walk(os_folder):
                file_amount += len(files)
                root_arr = root.split(os.sep)
                root_arr = root_arr[root_arr.index(folder_name):]
                encrypto_root = f"{path}{'/'.join(root_arr)}"
                if encrypto_root[-1] != "/":
                    encrypto_root = f"{encrypto_root}/"
                for dir in dirs:
                    print(f"Creating folder: {encrypto_root}{dir}")
                    futures[folder_executor.submit(self.create_folder, f"{encrypto_root}{dir}")] = f"{encrypto_root}{dir}"
                results, success = self._complete_cloud_threads(futures)
                if not success:
                    raise Exception("Failed to upload folders in given folder.")
                futures = {}

        # Skip file upload if there are no files
        if file_amount == 0:
            print(f"No files to upload in folder: {os_folder}")
            return True

        # Create all files
        futures = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=file_amount if file_amount < 15 else 15) as file_executor:
            for root, _, files in os.walk(os_folder):
                root_arr = root.split(os.sep)
                root_arr = root_arr[root_arr.index(folder_name):]
                encrypto_root = f"{path}{'/'.join(root_arr)}"
                for file in files:
                    print(f"Uploading file: {encrypto_root}/{file}")
                    futures[file_executor.submit(self.upload_file, os.path.join(root, file), encrypto_root)] = f"{encrypto_root}-{file}"
            results, success = self._complete_cloud_threads(futures)
            if not success:
                raise Exception("Failed to upload files in folders.")
        return True
    
    def download_file(self, path, isopen=False):
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
            
            # Merge and decrypt the data
            if not data:
                raise ValueError(f"No data downloaded for file {path}.")
            try:
                encrypted_data = self._merge(data, len(self.clouds))
                data = self._decrypt(encrypted_data)
            except Exception as e:
                raise Exception(f"Error merging or decrypting data for file {path}: {e}")

            if not isopen:
                # Set the destination path to the Downloads folder
                downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
                dest_path = os.path.join(downloads_folder, file.data.get("name"))
                file_name, ext = os.path.splitext(dest_path)
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = f"{file_name} ({counter}){ext}"
                    counter += 1
            else:
                # Set the destination path to the temporary folder
                dest_path = self.get_temp_file_path(file.data.get("name"))

            # Write the reconstructed file to the destination path
            try:
                with open(dest_path, 'wb') as output:
                    output.write(data)
                print(f"File successfully reconstructed into '{dest_path}'.")
            except Exception as e:
                raise Exception(f"Error writing file to {dest_path}: {e}")
            return True

        except ValueError as ve:
            print(f"ValueError: {ve}")
        except FileNotFoundError as fnfe:
            print(f"FileNotFoundError: {fnfe}")
        except Exception as e:
            print(f"Unexpected error while downloading file: {e}")
        return False

    def open_file(self, path):
        """
        Downloads the file from the specified path and opens it with the relevant editor.
        The file is downloaded to the persistent temporary folder.
        @param path: The path to the file in the EncryptoSphere hierarchy.
        """
        try:
            # Download the file
            print(f"Downloading file from path: {path}")
            success = self.download_file(path, isopen=True)
            if not success:
                raise Exception(f"Failed to download file from path: {path}")

            # Get the downloaded file's metadata
            file = self.fs.get(path)
            if not file:
                raise Exception(f"File not found in file descriptor: {path}")

            # Determine the temporary file path
            temp_file_path = self.get_temp_file_path(file.name)

            # Open the file with the default application
            print(f"Opening file: {temp_file_path}")
            os.startfile(temp_file_path)  # Windows-specific

        except Exception as e:
            print(f"Error opening file: {e}")

    def download_folder(self, folder_path: str, parent_local_path: str = None):
        """
        Downloads a folder and all its contents (including subfolders and files)
        from the cloud to the user's Downloads folder.
        @param folder_path: The path of the folder in the cloud.
        @param parent_local_path: The local path of the parent folder (used for recursion).
        """
        try:
            # Set the destination path to the Downloads folder if not provided
            if parent_local_path is None:
                downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
                folder_name = os.path.basename(folder_path.rstrip("/"))
                local_folder_path = os.path.join(downloads_folder, folder_name)
            else:
                folder_name = os.path.basename(folder_path.rstrip("/"))
                local_folder_path = os.path.join(parent_local_path, folder_name)
            counter = 1
            while os.path.exists(local_folder_path):
                local_folder_path = f"{local_folder_path} ({counter})"
                counter += 1

            # Create the local folder
            os.makedirs(local_folder_path, exist_ok=True)

            # Refresh the folder contents to ensure we have the latest data
            items = list(self.get_items_in_folder(folder_path))

            # Iterate through all items in the folder
            for item in items:
                item_path = item.get("path")
                item_name = item.get("name")
                item_type = item.get("type")

                # Construct the local path for the item
                local_path = os.path.join(local_folder_path, item_name)

                if item_type == "folder":
                    # Recursively download the subfolder
                    print(f"Creating subfolder: {local_path}")
                    self.download_folder(item_path, local_folder_path)
                elif item_type == "file":
                    # Download the file
                    print(f"Downloading file: {item_path}")
                    self.download_file(item_path)

                    # Move the downloaded file to the correct location
                    downloaded_file = os.path.join(os.path.expanduser("~"), "Downloads", os.path.basename(item_path))
                    if os.path.exists(downloaded_file):
                        shutil.move(downloaded_file, local_path)
                        print(f"Moved file to: {local_path}")
                    else:
                        raise FileNotFoundError(f"Downloaded file not found: {downloaded_file}")

            print(f"Folder '{folder_path}' successfully downloaded to: {local_folder_path}")

        except Exception as e:
            print(f"Error downloading folder '{folder_path}': {e}")
            raise


    def delete_file(self, path):
        """
        Deletes a specific file from the file descriptor.
        If the file cannot be deleted, an error is raised and displayed in a message box.
        @param path: The path to the file in the EncryptoSphere hierarchy.
        """
        file: CloudFile = self.fs.get(path)
        if file is None:
            raise Exception(f"Trying to delete a non-existent file: {path}")

        futures = {}
        for cloud in self.clouds:
            parts = file.get(cloud.get_name())
            for part in parts:
                futures[self.executor.submit(cloud.delete_file, part)] = cloud

        results, success = self._complete_cloud_threads(futures)

        if not success:
            failed_clouds = [cloud.get_name() for cloud, result in results if result is None]
            error_message = f"File Deletion Error: Failed to delete file parts."
            print(error_message)
            raise Exception(error_message)

        self.fs.pop(path)
        return True

    def delete_folder(self, folder_path):
        """
        Deletes a folder from all clouds.
        If any cloud fails, an error is raised.
        @param folder_path: The path to the folder in the file descriptor.
        """
        if folder_path == "/":
            raise Exception("Cannot delete the root folder.")

        folder = self.fs.get(folder_path)
        if not folder or not isinstance(folder, Directory):
            raise Exception(f"Folder '{folder_path}' does not exist.")

        errors = []
        for cloud in self.clouds:
            try:
                cloud.delete_folder(folder.get(cloud.get_name()))
            except Exception as e:
                errors.append(f"{cloud.get_name()}: {e}")

        # Remove from local fs if successful in all clouds
        if not errors:
            self.fs.pop(folder_path, None)
            topop = []
            for path in self.fs.keys():
                if path.startswith(folder_path):
                    topop.append(path)
            for path in topop:
                self.fs.pop(path)
            print(f"Folder '{folder_path}' deleted from all clouds and local fs.")
            return True
        else:
            error_message = "Folder Deletion Error: " + "; ".join(errors)
            print(error_message)
            raise Exception(error_message)
    
    def rename_item(self, old_path : str, new_name : str):
        """
        Renames an item (file or folder) in the EncryptoSphere file descriptor.
        @param old_path: The current path of the item to rename.
        @param new_name: The new name for the item.
        """
        item = self.fs.get(old_path)
        old_name = old_path.split("/")[-1]
        if not item:
            raise FileNotFoundError(f"Item with path {old_path} does not exist!")
        
        # Check if the new name is valid
        if not new_name or "/" in new_name or "\\" in new_name or ".." in new_name or "$" in new_name or "#" in new_name:
            raise ValueError("Invalid new name for the item.")
        
        # Create the new path
        parent_path = "/".join(old_path.split("/")[:-1])
        new_path = f"{parent_path}/{new_name}"
        parent_path = parent_path if parent_path != "" else "/"
        # Check if the new path already exists
        if self.fs.get(new_path):
            raise FileExistsError(f"An item with the name '{new_name}' already exists at {parent_path}.")
        
        for t in self.get_items_in_folder(parent_path):
            if t.get("name") == new_name:
                raise FileExistsError(f"An item with the name '{new_name}' already exists in the folder {parent_path}.")

        # Rename the item in all clouds
        futures = {}
        for cloud in self.clouds:
            if isinstance(item, Directory):
                futures[self.executor.submit(cloud.rename_folder, item.get(cloud.get_name()), new_name)] = cloud
            elif isinstance(item, CloudFile):
                # For files, we need to rename each part
                for index, part in enumerate(item.get(cloud.get_name())):
                    split_name = part.name.split(FILE_INDEX_SEPERATOR, 1)
                    if len(split_name) == 2:
                        new_file_name = f"{split_name[0]}{FILE_INDEX_SEPERATOR}{new_name}"
                    else:
                        new_file_name = new_name
                    if new_name == old_name:
                        raise ValueError("New name cannot be the same as the old name.")
                    futures[self.executor.submit(cloud.rename_file, part, new_file_name)] = cloud
        
        results, success = self._complete_cloud_threads(futures)
        if not success:
            raise Exception("Failed to rename item in some clouds.")
        
        appended = None
        for cloud,result in results:
            if isinstance(item, Directory):
                if appended is None:
                    appended = {cloud.get_name(): result}
                else:
                    appended[cloud.get_name()] = result
            elif isinstance(item, CloudFile):
                if appended is None:
                    appended = {cloud.get_name(): [result]}
                else:
                    if not appended.get(cloud.get_name()):
                        appended[cloud.get_name()] = []
                    appended[cloud.get_name()].append(result)

        self.fs.pop(old_path, None)  # Remove the old path from the file descriptor
        self.fs[new_path] = Directory(appended, new_path) if isinstance(item, Directory) else CloudFile(appended, new_path)
        return True
    
    def get_items_in_folder(self, path):
        folder = self.fs.get(path)
        if not folder:
            raise FileNotFoundError(f"Folder with path {path} does not exist!")
        
        # for item_path, item in self.fs.items():
        #     if item_path == '/':
        #         continue
        #     mydir = "/".join(item_path.split("/")[:-1])
        #     mydir = mydir if mydir != '' else '/'
        #     if mydir == path:
        #         yield item.get_data()
        
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
        added = []
        for folder_path, f in folders.items():
            dir = Directory(f, folder_path)
            added.append(folder_path)
            yield dir.get_data()
            self.fs[folder_path] = dir
            
        for file_path, parts in files.items():
            f = CloudFile(parts, file_path)
            added.append(file_path)
            yield f.get_data()
            self.fs[file_path] = f
        
        to_remove = []
        for item_path in self.fs.keys():
            item_folder = "/".join(item_path.split("/")[:-1])
            item_folder = item_folder if item_folder != '' else '/'
            if item_path != path and not item_path in added and item_folder == path:
                print(f"File was deleted: {item_path}")
                to_remove.append(item_path)
        
        for item_path in to_remove:
            self.fs.pop(item_path)
    
    def copy_file(self, file_path: str, destination_path: str, source_manager=None):
        """
        Copy and paste a file to a destination path.
        Downloads the file, checks for name conflicts, and uploads it to the destination path.
        If a name conflict exists, renames the file to 'Copy_of_<original_name>'.
        Skips the file if it cannot be copied due to errors.
        @param file_path: The path of the file to copy.
        @param destination_path: The destination folder path.
        @param source_manager: A cloudmanager that the file in file_path exists in, if none will use self
        """
        temp_path = None
        try:
            if source_manager is None:
                source_manager = self

            if not self.fs.get(destination_path) or not isinstance(self.fs.get(destination_path), Directory):
                raise FileNotFoundError(f"Destination path '{destination_path}' does not exist or is not a folder.")


            # Retrieve the file to copy
            file = source_manager.fs.get(file_path)
            if not file or not isinstance(file, CloudFile):
                raise FileNotFoundError(f"File '{file_path}' does not exist.")

            # Download the file
            print(f"Downloading file: {file_path}")
            source_manager.download_file(file_path, True)

            # Check for name conflicts
            original_name = file_path.split("/")[-1]
            new_name = original_name
            counter = 1

            # List existing files in the destination folder
            existing_files = {item["name"] for item in self.get_items_in_folder(destination_path)}
            dest_path = destination_path if destination_path != '/' else ''
            while new_name in existing_files or self.create_temporary_placeholder(f"{dest_path}{new_name}") is None:
                new_name = f"{original_name} ({counter})"
                counter += 1
            
            temp_path = f"{dest_path}{new_name}"
            # Get the temporary file path
            os_path = self.get_temp_file_path(original_name)

            # Upload the file to the destination
            print(f"Temporary file path: {os_path}")
            print(f"Uploading to: {destination_path}/{new_name}")
            self.upload_file(os_path, destination_path, new_name)

            # Add the new file name to the existing files set to avoid further conflicts
            existing_files.add(new_name)

            print(f"File '{file_path}' successfully copied to '{destination_path}/{new_name}'.")
            return True

        except FileNotFoundError as fnfe:
            print(f"File not found: {fnfe}. Skipping file '{file_path}'.")
        except Exception as e:
            print(f"Unexpected error while copying file '{file_path}': {e}. Skipping file.")
        finally:
            if temp_path:
                self.remove_temporary_placeholder(temp_path)
        return False

    def copy_folder(self, folder_path: str, destination_path: str, source_manager=None):
        """
        Copy and paste a folder and its contents to a destination path.
        Downloads the folder to a temporary location, checks for name conflicts,
        and uploads it to the destination path.
        If a name conflict exists, renames the folder to 'Copy_of_<original_name>'.
        Skips any folders that cannot be copied due to errors.
        @param folder_path: The path of the folder to copy.
        @param destination_path: The destination folder path.
        @param destination_manager: A cloudmanager that the file in file_path exists in, if none will use self
        """
        temp_path = None
        renamed_tmp_dir_folder = None
        try:
            if source_manager is None:
                source_manager = self

            # Validate the destination path
            if not self.fs.get(destination_path) or not isinstance(self.fs.get(destination_path), Directory):
                raise FileNotFoundError(f"Destination path '{destination_path}' does not exist or is not a folder.")

            # Retrieve the folder to copy
            folder = source_manager.fs.get(folder_path)
            if not folder or not isinstance(folder, Directory):
                raise FileNotFoundError(f"Folder '{folder_path}' does not exist.")

            # List existing items in the destination folder
            existing_items = {item["name"] for item in self.get_items_in_folder(destination_path)}

            # Check for name conflicts for the folder itself
            original_name = folder_path.split("/")[-1]
            new_folder_name = original_name
            counter = 1
            dest_path = destination_path if destination_path != '/' else ''
            while new_folder_name in existing_items or self.create_temporary_placeholder(f"{dest_path}{new_folder_name}") is None:
                new_folder_name = f"{original_name} ({counter})"
                counter += 1

            temp_path = f"{dest_path}{new_folder_name}"

            # Create a temporary directory for the folder
            tmp_dir = tempfile.mkdtemp(prefix="EncryptoSphere_FolderTransfer_", dir=self.get_temp_file_path())

            # Download the folder to the temporary directory
            print(f"Downloading folder '{folder_path}' to temporary location: {tmp_dir}")
            source_manager.download_folder(folder_path, tmp_dir)

            # Rename the folder in the temporary directory to match the new name
            renamed_tmp_dir_folder = os.path.join(tmp_dir, new_folder_name)
            os.rename(os.path.join(tmp_dir, original_name), renamed_tmp_dir_folder)
            print(f"Renamed folder in temporary location to: {renamed_tmp_dir_folder}")

            # Upload the folder from the temporary directory to the destination
            new_folder_path = f"{destination_path}/{new_folder_name}"
            print(f"Uploading folder from temporary location '{renamed_tmp_dir_folder}' to destination: {new_folder_path}")
            self.upload_folder(renamed_tmp_dir_folder, destination_path)

            print(f"Folder '{folder_path}' successfully copied to '{destination_path}'.")
            if os.path.exists(renamed_tmp_dir_folder):
                shutil.rmtree(renamed_tmp_dir_folder)
                print(f"Temporary directory '{renamed_tmp_dir_folder}' cleaned up.")
            return True
        
        except FileNotFoundError as fnfe:
            print(f"File not found: {fnfe}. Skipping folder '{folder_path}'.")
            if renamed_tmp_dir_folder is not None and os.path.exists(renamed_tmp_dir_folder):
                shutil.rmtree(renamed_tmp_dir_folder)
        except Exception as e:
            if renamed_tmp_dir_folder is not None and os.path.exists(renamed_tmp_dir_folder):
                shutil.rmtree(renamed_tmp_dir_folder)
            print(f"Unexpected error while copying folder '{folder_path}': {e}. Skipping folder.")
        finally:
            if temp_path:
                self.remove_temporary_placeholder(temp_path)
        return False
                
    @staticmethod
    def is_metadata_exists(cloud : CloudService, root : str, file_name : str) -> bool:
        """
        Checks if the metadata file exists in the cloud.
        @param cloud: The cloud service to check.
        @param root: The root directory name.
        @return: True if the metadata file exists, False otherwise.
        """
        try:
            files = cloud.list_files(cloud.get_session_folder(root), file_name)
            return len(list(files)) > 0
        except Exception as e:
            print(f"Error checking metadata existence: {e}")
            return False

    @staticmethod
    def download_metadata(cloud : CloudService, root : str, file_name : str):
        if not cloud.is_authenticated():
            raise Exception("Cloud is not authenticated")
        files = cloud.list_files(cloud.get_session_folder(root), file_name)
        metadata = None
        for file in files:
            metadata = file
            break
        if metadata is None:
            raise Exception("Failed to find metadata- run is_metadata_exists to check if metadata exists")
        return cloud.download_file(metadata)
    
    @staticmethod
    def upload_metadata(clouds : list[CloudService], root : str, metadata : dict, file_name : str):
        """
        Uploads the metadata to the cloud.
        @param cloud: The cloud service to upload to.
        @param root: The root directory name.
        @param metadata: The metadata dictionary to upload.
        @return: True if the upload is successful, False otherwise.
        """
        def upload(cloud : CloudService):
            if not cloud.is_authenticated():
                raise Exception("Cloud is not authenticated")
            metadata_json = json.dumps(metadata).encode('utf-8')
            return cloud.upload_file(metadata_json, file_name, cloud.get_session_folder(root))
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(clouds)) as executor:
            futures = [executor.submit(upload, cloud) for cloud in clouds]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()  # Wait for the upload to complete
                except Exception as e:
                    print(f"Error uploading metadata to cloud: {e}")
                    return False
            

    def load_metadata(self):
        """
        Downloads the filedescriptor from the clouds and sets it as this object's file descriptor.
        This function does NOT perform authentication or key creation — it only loads metadata.
        """
        #metadata = self._download_replicated("$META")
        # Download without using the replicated function since we did not set up self.fs yet
        if self.fs.get("/") is None:
            metadata = self.clouds[0].list_files(self.clouds[0].get_session_folder(self.root), "$META")
            for meta in metadata:
                if meta.get_name() == "$META":
                    metadata = self.clouds[0].download_file(meta)
                    print(f"Successfully downloaded metadata for session {self.root}.")
                    break
            
        else:
            metadata = self._download_replicated("$META")
        
        if not isinstance(metadata, bytes):
            self.metadata = {
                "encrypt": self.encrypt.get_name(),
                "split": self.split.get_name(),
                "order": self.cloud_name_list
            }
            if self.fs.get("/") is None:
                for cloud in self.clouds: # If there isn't a root folder, we are creating a session so self.clouds is accurate
                    cloud.upload_file(json.dumps(self.metadata).encode('utf-8'), "$META", cloud.get_session_folder(self.root))
            else:
                self._upload_replicated("$META", json.dumps(self.metadata).encode('utf-8'))
        else:
            self.metadata = json.loads(metadata)
            email = self.clouds[0].get_email() # We only support having the same email in all clouds for now
            for index,cloudname in enumerate(self.metadata.get("order")):
                if index >= len(self.clouds):
                    print(f"Adding cloud {cloudname} to session {self.root}")
                    self.clouds.append(CloudService.get_class(cloudname)(email))
                elif self.clouds[index].get_name() != cloudname:
                    print(f"Changing cloud order for session {self.root}")
                    self.clouds[index] = CloudService.get_class(cloudname)(email)
            if len(self.clouds) > len(self.metadata.get("order")):
                print(f"Removing extra clouds from session {self.root}")
                self.clouds = self.clouds[:len(self.metadata.get("order"))]
            self.cloud_name_list = self.metadata.get("order")
                
            if self.split.get_name() != self.metadata.get("split"):
                print(f"Changing splitting algorithm for session {self.root} to {self.metadata.get('split')}")
                self.split = Split.get_class(self.metadata.get("split"))()

            if self.encrypt.get_name() != self.metadata.get("encrypt"):
                print(f"Changing encryption algorithm for session {self.root} to {self.metadata.get('encrypt')}")
                self.encrypt = Encrypt.get_class(self.metadata.get("encrypt"))()

    def search_items_by_name(self, filter: str, path: str):
        """
        Search for files and folders by name across all clouds.
        @param filter: The filter string to search for.
        @param path: The folder path to start the search from.
        @return: A tuple containing two lists: one for files and one for folders.
        """

        # Get the starting folder object
        print("Searching for items by name...")
        start_folder = self.fs.get(path)
        if not start_folder:
            raise FileNotFoundError(f"Start folder '{path}' does not exist!")

        cloud = self.clouds[0]  
        try:
            # Get items matching the filter from the cloud
            items = cloud.get_items_by_name(filter, [start_folder.get(cloud.get_name())])
            for item in items:
                # Skip files that start with "$"
                if item.name.startswith("$"):
                    continue
                print(f"Found item: {item.name} in cloud {cloud.get_name()}")

                if isinstance(item, CloudService.File):
                    # Process files
                    split = item.name.split(FILE_INDEX_SEPERATOR)
                    if len(split) == 2 and split[0] != "1":
                        # Ignore parts with #2 or higher
                        continue

                    # Add file data to the files list
                    yield item

                elif isinstance(item, CloudService.Folder):
                    # Add folder data to the folders list
                    yield item

        except Exception as e:
            print(f"Error searching items in cloud '{cloud.get_name()}': {e}")
    
    def object_to_cloudobject(self, item : CloudService.CloudObject):
        """
        Enrich a CloudFile or Directory object by retrieving its full metadata, including the path.
        @param item: The File or Folder object to enrich.
        @return: The enriched object with the full metadata.
        """
        cloud = self.clouds[0] # TODO: use dropbox if available because it is much faster
        path = cloud.get_full_path(item, self.fs["/"].get(cloud.get_name()))
        
        # Create CloudFile or Directory object with the full path
        try:
            if isinstance(item, CloudService.File):
                parent_path  = "/".join(path.split("/")[:-1])
                parent_path = parent_path if parent_path != '' else '/'
                filename = item.name.split(FILE_INDEX_SEPERATOR)[-1]
                path = f"{parent_path}/{filename}" if parent_path != '/' else f"/{filename}"
                self._get_directory(parent_path) if parent_path != '' else self.fs["/"] # Call get_directory to store directory in self.fs
                list(self.get_items_in_folder(parent_path)) # Call get_items_in_folder to ensure the file is in the fs
            elif isinstance(item, CloudService.Folder):
                self._get_directory(path) # Call get_directory to store directory in self.fs
            return path
        except Exception as e: 
            print(e)
            raise Exception(f"Failed to convert object to cloud object: {e}")
