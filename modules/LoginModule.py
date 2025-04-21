import os
from argon2 import PasswordHasher
from argon2.low_level import hash_secret_raw, Type
from modules import Encrypt

class LoginModule:
    """
    This class handles secure account creation and login,
    using Argon2 for password hashing and a pluggable encryption module (like AES).
    """

    def __init__(self):
        self.ph = PasswordHasher()

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

    def login(self, input_password: str, salt: bytes, encrypted_data: bytes, encryption_type: str):
        """
        Attempt to decrypt user data using the password and encryption method.
        """
        encryptor_class = Encrypt.get_class(encryption_type)
        if encryptor_class is None:
            raise ValueError(f"Unsupported encryption type: {encryption_type}")
        encryptor = encryptor_class()

        key = self.create_key_from_password(input_password, salt)
        encryptor.set_key(encryptor.generate_key_from_key(key))

        try:
            decrypted_data = encryptor.decrypt(encrypted_data)
            return decrypted_data.decode()
        except Exception:
            raise ValueError("Invalid password or corrupted data.")


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