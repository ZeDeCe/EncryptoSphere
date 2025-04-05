from CloudManager import CloudManager
from FileDescriptor import FileDescriptor
from modules.Encrypt import Encrypt
from modules.Split import Split
from modules.CloudAPI.CloudService import CloudService
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes,serialization
import re
import os
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
        self.tfek = None
        self.public_key = None
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
            self.share_keys() # Can happen on a different thread now
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
        for cloud in self.clouds:
            folder = cloud.get_folder(self.root_folder)
            if folder:
                # try: # check it is shared with people
                #     cloud.get_members_shared(folder)
                # except:
                #     continue
                # This might have FEK
                key = self.check_key_status(cloud)
                if key:
                    my_key = key
                    break
            else:
                print(f"Cloud {cloud.get_name()} does not have the shared folder {self.root_folder}. Ignoring cloud for session.")
                self.clouds.pop(self.clouds.index(cloud)) # pop cloud from clouds list
        if my_key:
            # We have at least a single FEK
            key = self._decrypt(my_key)
            return key
        return False

    def sync_fek(self, key : bytes) -> None:
        self._upload_replicated("$FEK", self._encrypt(key), True)

        # Try deleting excess files - can happen on new thread
        try:
            self._delete_replicated(f"$TFEK", True)
        except:
            print("Failed to delete TFEK")
        try:
            self._delete_replicated(f"$PUBLIC", True)
        except:
            print("Failed to delete PUBLIC")

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
        fek = None
        try:
            fek = cloud.download_file(f"$FEK_{cloud.get_email()}", self.root_folder)
        except:
            pass
        if fek:
            return fek
        
        shared_secret = None
        tfek = None
        public_key = None

        # download_file raises errors if it fails
        try:
            shared_secret = cloud.download_file(f"$SHARED_{cloud.get_email()}", self.root_folder)
        except:
            pass
        try:
            tfek = cloud.download_file(f"$TFEK_{cloud.get_email()}", self.root_folder)
        except:
            pass
        # Don't download public key if we have shared key
        if not shared_secret:
            try:
                public_key = cloud.download_file(f"$PUBLIC_{cloud.get_email()}", self.root_folder)
            except:
                pass

        if shared_secret and tfek:
            private = self._decrypt(tfek)
            private = serialization.load_pem_private_key(
                private,
                password=None
            )
            shared_secret = private.decrypt(
                shared_secret,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            try:
                self._delete_replicated("$TFEK", True)
                self._delete_replicated("$SHARED", True)
                self._delete_replicated("$PUBLIC", True)
            except:
                print("Failed to delete temporary files, but successful key share")
            self.sync_fek(shared_secret)
            return self._encrypt(shared_secret)
        if not (tfek and public_key):
            self.upload_TFEK(cloud)
        return False
        
    def upload_TFEK(self, cloud : CloudService):
        """
        Uploads the TFEK and public key files to the shared folder to await answer
        @param cloud the cloud to use
        """
        if not self.tfek:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            self.tfek = self._encrypt(private_pem)
        
        if not self.public_key:
            public_key = private_key.public_key()
            self.public_key = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        cloud.upload_file(self.tfek, f"$TFEK_{cloud.get_email()}", self.root_folder)
        cloud.upload_file(self.public_key, f"$PUBLIC_{cloud.get_email()}", self.root_folder)
    
    def share_keys(self):
        """
        Look if there is a temporary public key file uploaded by a valid user
        share the shared key with that user by creating a temporary shared key
        """
        if self.loaded == False:
            return
        shared_key = self.encrypt.get_key()
        for cloud in self.clouds:
            public_keynames = filter(lambda name: name.startswith("$PUBLIC_"), cloud.list_files(self.root_folder))
            for keyname in public_keynames:
                username = keyname[8:]
                if username == "":
                    continue
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

    def test_access(self) -> bool:
        """
        Tests if there is still access to the session root folder and it is still a shared folder
        @return True if at least 1 folder is still shared and active on one of the clouds, False if none
        """
        for cloud in self.clouds:
            folder = cloud.get_folder(self.root_folder)
            if folder:
                try: # check it is shared with people
                    cloud.get_members_shared(folder)
                except:
                    continue
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
    
    def revoke_user_from_share(self, users):
        """
        Completely revokes a user from a shared session
        Will delete their FEK and unshare them from the folder
        If it is the last user, converts to a normal session
        @param users a dictionary in the format: {"cloudname": "email", ...}
        """
        pass
    
    def add_user_to_share(self, users):
        """
        Adds a new user to the shared session
        @param users a dictionary in the format: {"cloudname": "email", ...}
        """
        for cloud_name, email in users.items():
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
                self.users.append({cloud_name: email})

            except Exception as e:
                print(f"Failed to add user {email} to shared session on {cloud_name}: {e}")

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
        try:            
            members = cloud.get_members_shared(folder)
            print(f"Members: {members}")
            if not members or len(members) < 2:
                print(f"Folder {root} is not a valid session root, does not have at least 2 members shared")
                return False
        except Exception as e:
            print(f"Error checking shared status for folder {root}: {e}")
            return False

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
        