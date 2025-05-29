import os
from argon2 import PasswordHasher
from argon2.low_level import hash_secret_raw, Type
from modules import Encrypt
import hashlib
import json
from modules.CloudAPI import CloudService
from CloudManager import CloudManager
LOGIN_META_FILENAME = "$LOGIN_META"
class LoginManager:
    """
    This class handles secure account creation and login,
    using Argon2 for password hashing and a pluggable encryption module (like AES).
    """

    def __init__(self):
        self.ph = PasswordHasher()
        self.login_metadata = None
        self.encryption_type = None
        self.salt = None
        self.encrypted_auth = None
        self.auth_hash = None

    def create_key_from_password(self, password: str, salt: bytes) -> bytes:
        return hash_secret_raw(
            secret=password.encode(),
            salt=salt,
            time_cost=2,
            memory_cost=102400,
            parallelism=8,
            hash_len=32,
            type=Type.ID
        )

    def create_account(self, password: str, username: str, email: str, encryption_type: str):
        """
        Encrypt user data using the selected encryption method and return the encryption parameters.
        """
        salt = os.urandom(16)

        # Get the appropriate encryption class based on encryption_type
        encryptor_class = Encrypt.get_class(encryption_type)
        if encryptor_class is None:
            raise ValueError(f"Unsupported encryption type: {encryption_type}")
        encryptor = encryptor_class()

        key = self.create_key_from_password(password, salt)
        encryptor.set_key(encryptor.generate_key_from_key(key))

        user_data = f"Username: {username}\nEmail: {email}".encode()
        encrypted_data = encryptor.encrypt(user_data)

        return {
            "salt": salt,
            "user_data": encrypted_data,
            "encryption_type": encryption_type
        }

    
    def login(self, input_password: str, salt: bytes, auth_encrypted_hex: str, auth_hash: str, encryption_type: str):
        """
        Authenticate password by decrypting the encrypted auth blob and comparing its hash.

        :param input_password: Password provided by user
        :param salt: Salt used for key derivation
        :param auth_encrypted_hex: The encrypted authentication blob (hex-encoded)
        :param auth_hash: The expected SHA-256 hash of the decrypted blob
        :param encryption_type: The encryption algorithm name
        :raises ValueError: If authentication fails
        """
        encryptor_class = Encrypt.get_class(encryption_type)
        if encryptor_class is None:
            raise ValueError(f"Unsupported encryption type: {encryption_type}")

        encryptor = encryptor_class()
        key = self.create_key_from_password(input_password, salt)
        encryptor.set_key(encryptor.generate_key_from_key(key))

        try:
            auth_encrypted = bytes.fromhex(auth_encrypted_hex)
            decrypted_blob = encryptor.decrypt(auth_encrypted)
            decrypted_hash = hashlib.sha256(decrypted_blob).hexdigest()
            
            if decrypted_hash != auth_hash:
                raise ValueError("Invalid password: hash mismatch.")
            return key
        except Exception as e:
            raise ValueError(f"Authentication failed: {e}")


    def load_login_metadata(self, password: str, cloud : CloudService, root : str):
        """
        Loads login metadata ($LOGIN_META) from cloud using CloudManager static helpers.
        If the metadata file does not exist — raises an error.
        """
        metadata_content = CloudManager.download_metadata(cloud, root, LOGIN_META_FILENAME)
        metadata = json.loads(metadata_content)

        self.login_metadata = metadata
        self.encryption_type = metadata.get("encrypt")
        self.salt = bytes.fromhex(metadata.get("salt"))
        self.encrypted_auth = bytes.fromhex(metadata.get("auth_encrypted"))
        self.auth_hash = metadata.get("auth_hash")


    
    def create_login_metadata(self, password: str, encryption_type: str, split_type : str):
        """
        Creates and uploads $LOGIN_META metadata file to the cloud.
        Should be called when creating a new login session (e.g., during registration).
        """

        salt = os.urandom(16)
        encryptor_class = Encrypt.get_class(encryption_type)
        if encryptor_class is None:
            raise ValueError(f"Unsupported encryption type: {encryption_type}")
        encryptor = encryptor_class()

        key = self.create_key_from_password(password, salt)
        encryptor.set_key(encryptor.generate_key_from_key(key))

        auth_plaintext = os.urandom(16)
        encrypted_auth = encryptor.encrypt(auth_plaintext)
        auth_hash = hashlib.sha256(auth_plaintext).hexdigest()

        metadata = {
            "encrypt": encryption_type,
            "salt": salt.hex(),
            "auth_encrypted": encrypted_auth.hex(),
            "auth_hash": auth_hash,
            "split": split_type
        }

        # Save to memory
        self.login_metadata = metadata
        self.encryption_type = encryption_type
        self.salt = salt
        self.encrypted_auth = encrypted_auth
        self.auth_hash = auth_hash
    


"""""
def main():
    login_module = LoginModule()

    encryption_type = "AES"

    username = "alice"
    email = "alice@example.com"
    password = "securepassword123"

    print(f"Creating account using {encryption_type}...")
    account_data = login_module.create_account(password, username, email, encryption_type)
    print("Account created successfully!\n")

    print("Logging in...")
    try:
        decrypted_info = login_module.login(
            input_password="securepassword123",
            salt=account_data["salt"],
            encrypted_data=account_data["user_data"],
            encryption_type=account_data["encryption_type"]
        )
        print("Login successful! Decrypted data:")
        print(decrypted_info)
    except ValueError as e:
        print("Login failed:", str(e))
    
if __name__ == "__main__":
    main()
"""