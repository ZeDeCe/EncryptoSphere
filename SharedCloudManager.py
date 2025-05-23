from CloudManager import CloudManager
from FileDescriptor import FileDescriptor
from modules.Encrypt import Encrypt
from modules.Split import Split
from modules.CloudAPI.CloudService import CloudService
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes,serialization
from CloudObjects import Directory, CloudFile
import re
from uuid import uuid4
import concurrent.futures
from dotenv import load_dotenv
load_dotenv()

class SharedCloudManager(CloudManager):
    """
    This class holds a shared session using a list of clouds, encryption method, split method, and a filedescriptor
    """

    # Shared folder names are comprised of 2 parts: FOLDERNAME_ENCRSH
    shared_suffix = "_ENCRSH"

    
    def __init__(self, shared_with : list[dict] | None, root_folder : Directory | None, clouds : list[CloudService], root : str, split : Split, encrypt : Encrypt):
        """
        Initialize sharedcloudmanager
        Pass either shared_with or root_folder, but not both
        Passing shared_with creates a new session with the emails provided, passing root_folder initializes an already existing session
        @param shared_with a list of dictionaries as such: [{"Cloud1Name":"email", "Cloud2Name":"email", ...}, ...] or None for an existing session
        @param root_folder the directory to use as the root folder if the session already exists
        """
        assert (shared_with is None and not root_folder is None) or (not shared_with is None and root_folder is None)
        super().__init__(clouds, root, split, encrypt)
        self.root = f"{self.root}{SharedCloudManager.shared_suffix}"
        self.users = []
        self.loaded = False
        self.uid = None
        self.is_owner = False
        self.root_folder = root_folder
        if root_folder:
            self.fs["/"] = root_folder
        if shared_with:
            self.users = shared_with
            self.emails_by_cloud = {}
            for user in self.users:
                for cloud,email in user.items():
                    if self.emails_by_cloud.get(cloud):
                        self.emails_by_cloud[cloud].append(email) 
                    else:
                         self.emails_by_cloud[cloud] = [email]

    def authenticate(self):
        try:
            for cloud in self.clouds:
                cloud.authenticate_cloud()
        except:
            print("One of the clouds provided cannot authenticate for shared session")
            return False
        key = None
        
        
        if self.users:
            # This is a new session to be created
            try:
                key = self.create_new_session()
                if not key:
                    return False
                self.load_metadata()
                self.encrypt.set_key(key)
            except:
                return False
        else:
            # This session already exists (and might not be ours)
            key = self.load_session()
            
            # Set UID
            files = self.clouds[0].list_files(self.root_folder.get(self.clouds[0].get_name()), "$UID")
            for file in files:
                self.uid = f"{self.root.replace(SharedCloudManager.shared_suffix, '')}${file.get_name()[5:]}"
                break
            if self.uid is None:
                print("Cannot get UID for cloud manager")
                return False
            
            if not key: # Waiting for TFEK signing
                return False
            # load_metadata changes encryption and splitting classes
            self.load_metadata()
            self.encrypt.set_key(key)

        if key:
            
            self.is_owner = self.clouds[0].get_owner(self.root_folder.get(self.clouds[0].get_name())) == self.clouds[0].get_email()
            # loaded from this point
            self.loaded = True
            self.share_keys()
            return True
        print("Failed to authenticate shared session")
        return False
    

    def user_is_owner(self) -> bool:
        """
        Returns True if the current user is the owner of the session, False otherwise
        """
        return self.is_owner

    def create_new_session(self) -> bytes:
        """
        Create a first time share, generate a shared key and upload FEK
        """
        uuid = uuid4().hex
        futures = {}
        for cloud in self.clouds:
            try:
                futures[self.executor.submit(cloud.create_shared_session, self.root, self.emails_by_cloud[cloud.get_name()])] = cloud.get_name()
            except:
                print(f"Failed to create shared folder {self.root}")
                return False
        
        folders = {}
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
            self.root_folder = self.fs["/"]
        except Exception as e:
            print(f"Error during authentication, loading of file descriptor: {e}")
            return False
        self.uid = f"{self.root.replace(SharedCloudManager.shared_suffix, '')}${uuid}"
        self._upload_replicated(f"$UID_{uuid}",uuid.encode())
        key = self.encrypt.generate_key()
        self.executor.submit(self._upload_replicated, "$FEK", self._encrypt(key), True)
        return key

    def load_session(self) -> bytes | None:
        """
        Attempts to load an already existing shared session
        If returns false, the session is not ready for use since we have no encryption key
        If returns true, the session is ready for use and _encrypt() will now use the shared key.
        @return status, if failed to get the key for the session returns False otherwise True.
        """
        my_key = None
        # Make sure we do have a root folder
        assert self.root_folder and self.fs.get("/")

        # Try finding the key
        futures = []
        for cloud in self.clouds:
            futures.append(self.executor.submit(self.check_key_status, cloud))
        for future in concurrent.futures.as_completed(futures):
            try:
                result, sync = future.result()
                if result and isinstance(result, bytes):
                    # First key we get we break
                    my_key = result
                    if sync:
                        self.sync_fek(my_key)
                    break
            except Exception as e:
                pass
        if my_key:
            # We have at least a single FEK
            key = self._decrypt(my_key)
            return key
        return False

    def sync_fek(self, key : bytes) -> None:
        """
        @param key the encrypted key
        """
        futures = [
            self.executor.submit(self._upload_replicated, "$FEK", key, True),
            self.executor.submit(self._delete_replicated, "$TFEK", True),
            self.executor.submit(self._delete_replicated, "$PUBLIC", True),
            self.executor.submit(self._delete_replicated, "$SHARED", True),
        ]
        for future in futures:
            future.add_done_callback(lambda f: print(f"Error: {f.exception()}") if f.exception() else None)

    def check_key_status(self, cloud : CloudService) -> bytes | bool:
        """
        This function checks the status of the key transaction in the cloud given
        If it finds the shared key encrypted with the public key we already put, open it, encrypt the key with master to make FEK, upload FEK to folder, return encrypted key
        If it finds an FEK, return encrypted key
        If it finds TFEK but no response, return False
        If it finds nothing, upload a TFEK pair.
        @param cloud the cloud to use
        @return a tuple containing encrypted key if found and if a sync FEK is needed, if no key is found returns (False, False)
        """
        current_root = self.root_folder.get(cloud.get_name())
        special_files = cloud.list_files(current_root, "$")
        shared_file = None
        tfek = None
        public_file = None
        for file in special_files:
            if not cloud.get_email() in file.get_name():
                continue
            if file.get_name() == f"$FEK_{cloud.get_email()}":
                try:
                    return cloud.download_file(file), False
                except:
                    print("Found FEK but could not download")
                    continue
            if file.get_name() == f"$SHARED_{cloud.get_email()}":
                shared_file = file
            elif file.get_name() == f"$TFEK_{cloud.get_email()}":
                tfek = file
            elif file.get_name() == f"$PUBLIC_{cloud.get_email()}":
                public_file = file
            if shared_file is not None and tfek is not None:
                try:
                    shared_file = cloud.download_file(shared_file)
                    tfek = cloud.download_file(tfek)
                except:
                    print("Listed tfek and shared key but could not download them")
                    continue

                private = self._decrypt(tfek)
                private = serialization.load_pem_private_key(
                    private,
                    password=None
                )
                shared_secret = private.decrypt(
                    shared_file,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
                return self._encrypt(shared_secret), True
            
        if not tfek or not public_file:
            self.executor.submit(self.upload_TFEK, cloud)
        return False, False
        
    def upload_TFEK(self, cloud : CloudService):
        """
        Uploads the TFEK and public key files to the shared folder to await answer
        Generates a different key per cloud
        @param cloud the cloud to use
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        tfek = self._encrypt(private_pem)
        
        public_key = private_key.public_key()
        public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        cloud.upload_file(tfek, f"$TFEK_{cloud.get_email()}", self.root_folder.get(cloud.get_name()))
        cloud.upload_file(public_key, f"$PUBLIC_{cloud.get_email()}", self.root_folder.get(cloud.get_name()))
    
    def __share_keys_from_public(self, file : CloudService.File, cloud : CloudService):
        shared_key = self.encrypt.get_key()
        username = file.get_name()[8:]
        if username == "":
            return False
        
        # Check if the username is actually shared
        pem = cloud.download_file(file)
        public = serialization.load_pem_public_key(
            pem
        )
        response = public.encrypt(
            shared_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        cloud.upload_file(response, f"$SHARED_{username}", self.root_folder.get(cloud.get_name()))

    def __share_keys_cloud(self, cloud : CloudService):
        files = list(cloud.list_files(self.root_folder.get(cloud.get_name()), "$"))
        shared = list(map(lambda f: f.get_name()[8:], filter(lambda f: f.get_name().startswith("$SHARED_"), files)))
        public = filter(lambda f: f.get_name().startswith("$PUBLIC_"), files)

        for file in public:
            if file.get_name()[8:] not in shared:
                self.executor.submit(self.__share_keys_from_public, file, cloud)

        if self.is_owner:
            feks = list(map(lambda f: f.get_name()[5:], filter(lambda f: f.get_name().startswith("$FEK_"), files)))
            files = filter(lambda f: f.get_name().startswith("$SHARED_"), files)
            for file in files:
                if file.get_name()[8:] in feks:
                    print(f"Deleting shared file {file.get_name()}")
                    self._delete_replicated(file.get_name(), False)


    def share_keys(self):
        """
        Look if there is a public key file uploaded by a valid user
        share the shared key with that user by creating a temporary shared key
        """
        if self.loaded == False:
            return
        for cloud in self.clouds:
            self.executor.submit(self.__share_keys_cloud, cloud)

    def test_access(self) -> bool:
        """
        Tests if there is still access to the session root folder and it is still a shared folder
        @return True if all folders are still shared and active, False otherwise
        """
        futures = {}
        for cloud in self.clouds:
            # Try downloading a file that shouldn't exist to see if we don't raise exception
            futures[self.executor.submit(cloud.list_files, self.root_folder.get(cloud.get_name()), "$META")] = cloud
        
        results, success = self._complete_cloud_threads(futures)
        if not success:
            print("No access to one of the folders in the clouds")
            self.loaded = False
            return False
        return True
    
    def revoke_user_from_share(self, user : dict[str, str]):
        """
        Completely revokes a user from a shared session
        Will delete their FEK and unshare them from the folder
        If it is the last user, converts to a normal session
        @param user a dictionary in the format: {"cloudname": "email", ...}
        """
        # Check if the current user is the owner of the shared session
        if not self.user_is_owner():
            raise Exception("Error: Only the owner of the shared session can revoke users.")
    
        for cloud_name, email in user.items():
            # Find the cloud service by name
            cloud = next((c for c in self.clouds if c.get_name() == cloud_name), None)
            if not cloud:
                print(f"Cloud {cloud_name} not found in the current session.")
                continue

            try:
                # Unshare the folder with the specified user
                root = self.root_folder.get(cloud_name)
                cloud.unshare_by_email(root, [email])
                print(f"User {email} revoked from share session on {cloud_name}.")

                # Delete the user's specific FEK file
                fek_file_name = f"$FEK_{email}"
                fek = cloud.list_files(root, fek_file_name)
                for f in fek:
                    fek = f
                    break
                if not fek:
                    raise FileNotFoundError(f"FEK file '{fek_file_name}' not found for user {email} on {cloud_name}.")
                try:
                    cloud.delete_file(fek)
                    print(f"Deleted FEK file '{fek_file_name}' for user {email} on {cloud_name}.")
                except Exception as e:
                    print(f"Failed to delete FEK file '{fek_file_name}' for user {email} on {cloud_name}: {e}")

                # Remove the user from the shared session
                if self.users:
                    self.users = [
                        user for user in self.users if not (cloud_name in user and user[cloud_name] == email)
                    ]

            except Exception as e:
                print(f"Failed to remove user {email} from shared session on {cloud_name}: {e}")
    
    def add_users_to_share(self, users : list[dict[str, str]]):
        """
        Adds multiple new users to the shared session
        @param users a list of dictionaries in the format: [{"cloudname": "email", ...}, ...]
        """
        for user in users:
            for cloud_name, email in user.items():
                # Find the cloud service by name
                cloud = next((c for c in self.clouds if c.get_name() == cloud_name), None)
                if not cloud:
                    print(f"Cloud {cloud_name} not found in the current session.")
                    continue

                try:
                    # Share the folder with the new user
                    root = self.root_folder.get(cloud_name)
                    cloud.share_folder(root, [email])
                    print(f"User {email} added to shared session on {cloud_name}.")
                    
                except Exception as e:
                    print(f"Failed to add user {email} to shared session on {cloud_name}: {e}")
                    user.pop(cloud_name, None)  # Remove the cloud from the user dictionary if sharing fails
            self.users.append(user)

    @staticmethod
    def is_valid_session_root(cloud : CloudService, root : CloudService.Folder) -> bool:
        """
        Checks if the folder root given in the cloud is a valid session root for SharedCloudManager
        Checks the following:
        1. The name of the folder is [name]_{shared_suffix}
        2. The folder is a shared folder
        3. The folder contains at least 1 file with the name $FEK_[SOMETHING]@[SOMETHING]
        4. The folder has at least 2 members shared
        @return if it is valid, True, otherwise False
        """

        name = root.name
        if not name.endswith(SharedCloudManager.shared_suffix):
            print(f"Folder {root} is not a valid session root, does not match pattern")
            return False
        # try:            
        #     members = cloud.get_members_shared(folder)
        #     print(f"Members: {members}")
        #     if not members or len(members) < 2:
        #         print(f"Folder {root} is not a valid session root, does not have at least 2 members shared")
        #         return False
        # except Exception as e:
        #     print(f"Error checking shared status for folder {root}: {e}")
        #     return False

        try:
            files = cloud.list_files(root, "$FEK")
            fek_pattern = r"\$FEK_.+?@.+"
            if not any([re.match(fek_pattern, file.name) for file in files]):
                print(f"Folder {root} is not a valid session root, does not contain a valid $FEK file")
                return False
        except Exception as e:
            print(f"Error listing files in folder {root}: {e}")
            return False

        # If all checks pass, the folder is valid
        return True
    
    def get_uid(self):
        return self.uid
    

    def get_shared_emails(self) -> list[str]:
        """
        Returns the emails of the users shared in the session
        @param cloud_name the name of the cloud to get the emails from
        @return a list of emails of the users shared in the session
        """
        cloud = self.clouds[0]
        feks = cloud.list_files(self.root_folder.get(cloud.get_name()), "$FEK")
        users = set()
        self.users = []
        for fek in feks:
            if not re.match(r"\$FEK_.+?@.+", fek.get_name()):
                continue
            email = fek.get_name()[5:]
            if email == "" or email == cloud.get_email():
                continue
            users.add(email)
        for user in users:
            u = {}
            for cloud in self.clouds:
                    u[cloud.get_name()] = user
            self.users.append(u)
        return self.users
    
    def delete_session(self):
        """
        Deletes the shared session by leaving the shared folders in all clouds.
        If the user is the owner, raises an error.
        """
        if self.user_is_owner():
            raise Exception("Error: Cannot leave the shared folder as the owner. Unshare or delete the folder instead.")

        for cloud in self.clouds:
            folder = self.root_folder.get(cloud.get_name())
            if folder and folder.is_shared():
                print(f"Leaving shared folder '{folder.name}' on cloud '{cloud.get_name()}'.")
                cloud.leave_shared_folder(folder)

        print(f"Shared session '{self.root}' deleted successfully.")