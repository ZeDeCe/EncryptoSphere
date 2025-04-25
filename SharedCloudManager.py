from CloudManager import CloudManager
from FileDescriptor import FileDescriptor
from modules.Encrypt import Encrypt
from modules.Split import Split
from modules.CloudAPI.CloudService import CloudService
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes,serialization
import re
import concurrent.futures
from dotenv import load_dotenv
load_dotenv()

class SharedCloudManager(CloudManager):
    """
    This class holds a shared session using a list of clouds, encryption method, split method, and a filedescriptor
    """
    def __init__(self, shared_with : list[dict] | None, *args, **kwargs):
        """
        Initialize sharedcloudmanager
        @param shared_with a list of dictionaries as such: [{"Cloud1Name":"email", "Cloud2Name":"email", ...}, ...] or None for an existing session
        """
        super().__init__(*args, **kwargs)
        self.users = None
        self.loaded = False
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
            return False
        key = None
        if self.users:
            # This is a new session to be created
            try:
                key = self.create_new_session()
                self.encrypt.set_key(key)
                self.fd = FileDescriptor(None, None, self.encrypt.get_name(), self.split.get_name())
                self.sync_fd()
            except:
                return False
        else:
            # This session already exists (and might not be ours)
            key = self.load_session()
            if not key: # Waiting for TFEK signing
                return False
            self.fd = FileDescriptor(None, self._download_replicated("$FD_META"))
            files_enc = self._download_replicated("$FD")
            enc_cls = Encrypt.get_class(self.fd.get_encryption_signature())
            self.encrypt = enc_cls(key)
            split_cls = Split.get_class(self.fd.get_split_signature())
            self.split = split_cls()
            self.fd.set_files(self._decrypt(files_enc))
        if key:
            self.loaded = True
            self.share_keys()
            return True
        return False
    
    def create_new_session(self) -> bytes:
        """
        Create a first time share, generate a shared key and upload FEK
        """
        for cloud in self.clouds:
            folder = None
            try:
                folder = cloud.get_folder(self.root_folder)
            except:
                # A complete new session
                cloud.create_shared_folder(self.root_folder, self.emails_by_cloud[cloud.get_name()])
                continue

            # The folder exists, it must not have shared members or be shared
            members = cloud.get_members_shared(folder)
            if members == False: # even if members is empty, the FEK should be there if we made the session
                # The folder exists but is not shared, we are transforming a regular session or folder
                # to a shared session.
                cloud.share_folder(folder, self.emails_by_cloud[cloud.get_name()])
            else:
                # The folder is already shared, this is already a shared session
                raise Exception("Attempting to create a shared session from an already existing shared root folder")
        key = self.encrypt.generate_key()
        self.sync_fek(key)
        return key

    def load_session(self) -> bytes | None:
        """
        Attempts to load an already existing shared session
        If returns false, the session is not ready for use since we have no encryption key
        If returns true, the session is ready for use and _encrypt() will now use the shared key.
        @return status, if failed to get the key for the session returns False otherwise True.
        """
        my_key = None
        
        # Try finding the key
        futures = []
        for cloud in self.clouds:
            folder = cloud.get_folder(self.root_folder)
            if folder:
                futures.append(self.executor.submit(self.check_key_status, cloud))
            else:
                print(f"Cloud {cloud.get_name()} does not have the shared folder {self.root_folder}. Ignoring cloud for session.")
                self.clouds.pop(self.clouds.index(cloud)) # pop cloud from clouds list
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if result and isinstance(result, bytes):
                    # First key we get we break
                    my_key = result
                    break
            except Exception as e:
                pass
        if my_key:
            # We have at least a single FEK
            key = self._decrypt(my_key)
            self.sync_fek(key)
            return key
        return False

    def sync_fek(self, key : bytes) -> None:
        futures = [
            self.executor.submit(self._upload_replicated, "$FEK", self._encrypt(key), True),
            self.executor.submit(self._delete_replicated, "$TFEK", True),
            self.executor.submit(self._delete_replicated, "$PUBLIC", True)
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
        @return the encrypted key if found, if not then False
        """
        futures = {
            self.executor.submit(cloud.download_file, f"$FEK_{cloud.get_email()}", self.root_folder) : "fek",
            self.executor.submit(cloud.download_file, f"$SHARED_{cloud.get_email()}", self.root_folder) : "shared_secret",
            self.executor.submit(cloud.download_file, f"$TFEK_{cloud.get_email()}", self.root_folder) : "tfek",
            self.executor.submit(cloud.download_file, f"$PUBLIC_{cloud.get_email()}", self.root_folder) : "public"
        }
        files = {}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if futures[future] == "fek" and isinstance(result, bytes):
                for f in futures:
                    if not f.done():
                        f.cancel()
                return result
            if isinstance(result, Exception):
                print(f"File not found: {result}")
                result = None
            files[futures[future]] = result

        if files.get("shared_secret") and files.get("tfek"):
            private = self._decrypt(files.get("tfek"))
            private = serialization.load_pem_private_key(
                private,
                password=None
            )
            shared_secret = private.decrypt(
                files.get("shared_secret"),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return self._encrypt(shared_secret)
        if not (files.get("tfek") and files.get("public")):
            self.executor.submit(self.upload_TFEK, cloud)
        return False
        
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
        cloud.upload_file(tfek, f"$TFEK_{cloud.get_email()}", self.root_folder)
        cloud.upload_file(public_key, f"$PUBLIC_{cloud.get_email()}", self.root_folder)
    
    def __share_keys_from_public(self, keyname : bytes, cloud : CloudService):
        shared_key = self.encrypt.get_key()
        username = keyname[8:]
        if username == "":
            return False
        
        # Check if the username is actually shared
        pem = cloud.download_file(keyname, self.root_folder)
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
        cloud.upload_file(response, f"$SHARED_{username}", self.root_folder)

    def __share_keys_cloud(self, cloud : CloudService):
        public_keynames = filter(lambda name: name.startswith("$PUBLIC_"), cloud.list_files(self.root_folder))

        for keyname in public_keynames:
            self.executor.submit(self.__share_keys_from_public, keyname, cloud)

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
        @return True if at least 1 folder is still shared and active on one of the clouds, False if none
        """
        for cloud in self.clouds:
            folder = cloud.get_folder(self.root_folder)
            if folder and folder.shared:
                return True
        return False
    
    # Override start sync thread, we do not sync FD to cloud on a timer
    # We sync every operation
    def start_sync_thread(self):
        pass

    def stop_sync_thread(self):
        pass

    # In shared manager we do not use OS to store files
    # Instead each operation shares the FD so everyone else can have it
    def sync_fd(self):
        super().sync_to_clouds()
    
    def revoke_user_from_share(self, user : dict[str, str]):
        """
        Completely revokes a user from a shared session
        Will delete their FEK and unshare them from the folder
        If it is the last user, converts to a normal session
        @param user a dictionary in the format: {"cloudname": "email", ...}
        """
        for cloud_name, email in user.items():
            # Find the cloud service by name
            cloud = next((c for c in self.clouds if c.get_name() == cloud_name), None)
            if not cloud:
                print(f"Cloud {cloud_name} not found in the current session.")
                continue

            try:
                # Unshare the folder with the specified user
                folder = cloud.get_folder(self.root_folder)
                cloud.unshare_by_email(folder, [email])
                print(f"User {email} revoked from share session on {cloud_name}.")

                # Delete the user's specific FEK file
                fek_file_name = f"$FEK_{email}"
                try:
                    cloud.delete_file(fek_file_name, self.root_folder)
                    print(f"Deleted FEK file '{fek_file_name}' for user {email} on {cloud_name}.")
                except Exception as e:
                    print(f"Failed to delete FEK file '{fek_file_name}' for user {email} on {cloud_name}: {e}")

                # Remove the user from the shared session
                if self.users:
                    self.users = [
                        user for user in self.users if not (cloud_name in user and user[cloud_name] == email)
                    ]

                """
                # Check if there are any remaining shared users
                remaining_members = cloud.get_members_shared(folder)
                if not remaining_members or len(remaining_members) < 2:
                    # If no more shared users, delete the global FEK and convert to a normal session
                    print(f"No more shared users in the session for {cloud_name}. Converting to a normal session.")
                    cloud.delete_file("$FEK", self.root_folder)  # Delete the global FEK file
                    cloud.unshare_folder(folder)  # Unshare the folder completely
                    print(f"Session on {cloud_name} converted to a normal session.")
                """

            except Exception as e:
                print(f"Failed to add user {email} to shared session on {cloud_name}: {e}")
    
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
                    folder = cloud.get_folder(self.root_folder)
                    cloud.share_folder(folder, [email])
                    print(f"User {email} added to shared session on {cloud_name}.")

                    # Update self.users to include the new user
                    if self.users is None:
                        self.users = []
                    
                except Exception as e:
                    print(f"Failed to add user {email} to shared session on {cloud_name}: {e}")
                    user.pop(cloud_name, None)  # Remove the cloud from the user dictionary if sharing fails
            self.users.append(user)

    @staticmethod
    def is_valid_session_root(cloud : CloudService, root : CloudService.Folder) -> bool:
        """
        Checks if the folder root given in the cloud is a valid session root for SharedCloudManager
        Checks the following:
        1. The name of the folder is [name]_ENCRYPTOSPHERE_SHARE
        2. The folder is a shared folder
        3. The folder contains at least 1 file with the name $FEK_[SOMETHING]@[SOMETHING]
        4. The folder has at least 2 members shared
        @return if it is valid, True, otherwise False
        """
         # Ensure the root includes the base path
        folder = root
        root = root.path
        # base_path = os.getenv("ENCRYPTO_ROOT")
        # if not root.startswith(base_path):
        #     root = f"{base_path}{root}"
        
        if not root.endswith("_ENCRYPTOSPHERE_SHARE") or not root.startswith("/"):
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
            files = cloud.list_files(root)
            fek_pattern = r"\$FEK_.+?@.+"
            if not any([re.match(fek_pattern, file) for file in files]):
                print(f"Folder {root} is not a valid session root, does not contain a valid $FEK file")
                return False
        except Exception as e:
            print(f"Error listing files in folder {root}: {e}")
            return False

        # If all checks pass, the folder is valid
        return True
    

    def get_shared_emails(self) -> list[str]:
        """
        Returns the emails of the users shared in the session
        @param cloud_name the name of the cloud to get the emails from
        @return a list of emails of the users shared in the session
        """
        return self.users