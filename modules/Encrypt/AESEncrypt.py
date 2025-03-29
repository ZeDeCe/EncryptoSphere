from .Encrypt import Encrypt
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
import hashlib

class AESEncrypt(Encrypt):

    def generate_key_from_key(self, key : bytes) -> bytes:
        """
        Generate an AES key using Argon2id or another suitable method
        for secure key generation (here we use a simple example).
        This key will be used for AES encryption and decryption.
        If the key length is not 32 bytes, we adjust it using SHA-256.
        """
        # Ensure key is 32 bytes long by hashing it with SHA-256
        return hashlib.sha256(key).digest()
    
    def generate_key(self) -> bytes:
        """
        Generate a 32-byte AES key using SHA-256.
        """
        # Generate a random 16-byte value and hash it to create a 32-byte key
        return hashlib.sha256(get_random_bytes(16)).digest()
        

    def encrypt(self, data: bytes) -> bytes:
        """
        Encrypt the data using AES encryption with the stored key.
        """
        cipher = AES.new(self.key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return cipher.nonce + tag + ciphertext

    def decrypt(self, data: bytes) -> bytes:
        """
        Decrypt the data using AES decryption with the stored key.
        """
        nonce = data[:16]
        tag = data[16:32] 
        ciphertext = data[32:]

        cipher = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)

    @staticmethod
    def get_name() -> str:
        """
        Return the encryption method name (AES).
        """
        return "AES"


"""
def main():
    \"\"\"
    Main function to test the implementation.
    \"\"\"
    # Example key generation (in reality, this would be from Argon2id)
    raw_key = b"11111111111111111111111111111111"
    
    # Create encryption object with the key
    aes = AESEncrypt(raw_key)

    print(f"Encryption Method: {aes.get_name()}")
    print(f"Original Key (Raw): {raw_key}")
    print(f"Processed Key (SHA-256): {aes.key.hex()}")  # Display the processed key

    # Data to encrypt
    plaintext = b"Hello, this is a secret message!"
    print(f"\nOriginal Data: {plaintext}")

    # Encrypt the data
    encrypted_data = aes.encrypt(plaintext)
    print(f"Encrypted Data (Hex): {encrypted_data.hex()}")

    # Decrypt the data
    decrypted_data = aes.decrypt(encrypted_data)
    print(f"Decrypted Data: {decrypted_data}")

    # Check that decryption matches the original
    assert decrypted_data == plaintext, "ERROR: Decryption failed!"
    print("\nEncryption and Decryption Successful!")

if __name__ == "__main__":
    main()
"""