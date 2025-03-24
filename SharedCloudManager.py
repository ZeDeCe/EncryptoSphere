from CloudManager import CloudManager
from modules.CloudAPI.CloudService import CloudService
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes,serialization

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
        if(not super().authenticate()):
            return False
        if self.users:
            # This is a new session to be created
            try:
                self.create_new_session()
            except:
                return False
        else:
            # This session already exists (and might not be ours)
            self.loaded = self.load_session()
        return self.loaded
    
    def create_new_session(self):
        """
        Create a first time share, generate a shared key and upload FEK
        """
        for cloud in self.clouds:
            folder = cloud.get_folder(self.root_folder)
            if not folder:
                # A complete new session
                cloud.create_shared_folder(self.root_folder, self.emails_by_cloud[cloud.get_name()])
                continue

            # The folder exists, it must not have shared members or be shared
            members = cloud.get_members_shared(folder)
            if members == False: # even if members is empty, the FEK should be there if we made the session
                # The folder exists but is not shared, we are transforming a regular session or folder
                # to a shared session.
                cloud.share_folder(self.root_folder, self.emails_by_cloud[cloud.get_name()])
            else:
                # The folder is already shared, this is already a shared session
                raise Exception("Attempting to create a shared session from an already existing shared root folder")
        
        shared_key = self.encrypt.generate_key()
        encrypted_sk = self._encrypt(shared_key) # encrypted with master key
        self._upload_replicated("$FEK",encrypted_sk,True)
        self.encrypt.set_key(shared_key)

    def load_session(self) -> bool:
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
                try: # check it is shared with people
                    cloud.get_members_shared(folder)
                except:
                    continue
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
            real_key = self._decrypt(my_key)
            self.encrypt.set_key(real_key)

            # We can send this to it's own thread:
            self.sync_fek(my_key)
            return True
        return False

            
    def sync_fek(self, encrypted_key : bytes) -> None:
        self._upload_replicated("$FEK", encrypted_key, True)

        # Try deleting excess files
        for cloud in self.clouds:
            try:
                cloud.delete_file(f"$TFEK_{cloud.get_email()}")
            except:
                pass
            try:
                cloud.delete_file(f"$PUBLIC_{cloud.get_email()}")
            except:
                pass


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
        fek = cloud.download_file(f"$FEK_{cloud.get_email()}", self.root_folder)
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
            shared_secret = self._encrypt(shared_secret)
            self.sync_fek(shared_secret)
            return shared_secret
        if tfek and public_key:
            return False
        
        self.upload_TFEK(cloud)
        
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
                username = ""
                try:
                    username = keyname[8:]
                except:
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
                cloud.upload_file(response, "$SHARED_{username}", self.root_folder)

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
    
    # def pull_fek(self):
    #     """
    #     Assuming we already have a ready FEK, pull it from all clouds and sync it
    #     """
    #     fek_list = []
    #     for cloud in self.clouds:
    #         fek_list.append(self._decrypt(cloud.download_file(f"$FEK_{cloud.get_email()}", self.root_folder)))
    #     status, shared_key = self._check_replicated_integrity(fek_list)
    #     if not status:
    #         # for now raising exception, later can do error handling here
    #         raise Exception("FEK got corrupted!")
    #     self.encrypt.set_key(shared_key)
    
    # Since each session is with 1 user only right now, revoke_user will just call unshare_file

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
