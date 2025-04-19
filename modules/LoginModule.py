import os
from argon2 import PasswordHasher
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class LoginModule:
    """
    This class handles secure account creation and login,
    using Argon2 for password hashing and AES-GCM for encryption.
    """

    def __init__(self):
        self.ph = PasswordHasher()  # Argon2 password hasher

    def create_key_from_password(self, password: str, salt: bytes) -> bytes:
        """
        Create a 32-byte encryption key from a password using Argon2.
        The password is hashed and then truncated to 32 bytes.
        """
        hashed_password = self.ph.hash(password)
        return hashed_password.encode()[:32]  # AES-256 requires 32-byte key

    def create_account(self, password: str, username: str, email: str):
        """
        Encrypt user data (username + email) using AES-GCM and return the encryption parameters.
        """
        salt = os.urandom(16)   # Salt for key derivation
        nonce = os.urandom(12)  # 12-byte nonce for AES-GCM

        key = self.create_key_from_password(password, salt)

        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend())
        encryptor = cipher.encryptor()

        user_data = f"Username: {username}\nEmail: {email}".encode()
        encrypted_data = encryptor.update(user_data) + encryptor.finalize()

        return {
            "salt": salt,
            "nonce": nonce,
            "tag": encryptor.tag,
            "user_data": encrypted_data
        }

    def login(self, input_password: str, salt: bytes, nonce: bytes, tag: bytes, encrypted_data: bytes):
        """
        Attempt to decrypt encrypted user data using the provided password.
        Returns the decrypted user data if the password is correct.
        """
        key = self.create_key_from_password(input_password, salt)

        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=default_backend())
        decryptor = cipher.decryptor()

        try:
            decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
            return decrypted_data.decode()
        except Exception:
            raise ValueError("Invalid password or corrupted data.")


"""""
def main():
    login_module = LoginModule()

    # Create account
    print("Creating account...")
    username = "alice"
    email = "alice@example.com"
    password = "securepassword123"

    account_data = login_module.create_account(password, username, email)
    print("Account created successfully!")

    # Try to login
    print("\nLogging in...")
    try:
        decrypted_info = login_module.login(
            input_password="securepassword123",  # Try changing this to test failure
            salt=account_data["salt"],
            nonce=account_data["nonce"],
            tag=account_data["tag"],
            encrypted_data=account_data["user_data"]
        )
        print("Login successful!\nDecrypted data:")
        print(decrypted_info)
    except ValueError as e:
        print("Login failed:", str(e))

if __name__ == "__main__":
    main()
"""""