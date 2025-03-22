from CloudManager import CloudManager
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes,serialization

class SharedCloudManager(CloudManager):
    """
    This class holds a shared session using a list of clouds, encryption method, split method, and a filedescriptor
    """
    def __init__(self, new_session, shared_with : list[dict], *args, **kwargs):
        """
        Initialize sharedcloudmanager
        @param new_session True if to start a completely new session, False if the session already exists
        @param shared_with a list of dictionaries as such: [{"Cloud1Name":"email", "Cloud2Name":"email", ...}, ...]
        """
        super().__init__(self, *args, **kwargs)
        self.users = shared_with
        self.emails_by_cloud = {}
        for user in self.users:
            for cloud,email in user.items():
                self.emails_by_cloud[cloud] = email
        if(new_session):
            self.create_session()
        else:
            self.pull_fek()

    def create_session(self):
        """
        Create a first time share, generate a shared key and upload FEK
        """
        for cloud in self.clouds:
            folder_obj = cloud.create_folder(self.root_folder)
            shared_folder_obj = cloud.share(folder_obj)
        shared_key = Fernet.generate_key()
        encrypted_sk = self._encrypt(shared_key) # encrypted with master key
        for cloud in self.clouds:
            cloud.upload_file(encrypted_sk, f"$FEK_{cloud.get_email()}", self.root_folder)
        self.encrypt.set_key(shared_key)
    
    def pull_fek(self):
        """
        Assuming we already have a ready FEK, pull it from all clouds and sync it
        """
        fek_list = []
        for cloud in self.clouds:
            fek_list.append(self._decrypt(cloud.download_file(f"$FEK_{cloud.get_email()}", self.root_folder)))
        status, shared_key = self._check_replicated_integrity(fek_list)
        if not status:
            # for now raising exception, later can do error handling here
            raise Exception("FEK got corrupted!")
        self.encrypt.set_key(shared_key)
    
    # Since each session is with 1 user only right now, revoke_user will just call unshare_file
    def revoke_user(self, user, file_id):
        """
        Revokes a specific user from a specific file in a shared session
        @param user a dictionary in the format: {"cloudname": "email", ...}
        """
        self.unshare_file(file_id)

    def revoke_user_from_share(self, user):
        """
        Completely revokes a user from a shared session
        If it is the last user, converts to a normal session
        """
        pass

    def unshare_file(self, file_id):
        """
        Moves a file from a shared session to the main session
        """
        pass

    def unshare_folder(self):
        """
        Moves an entire folder from a shared session to the main session
        This function might take a long time to run
        """
        pass
