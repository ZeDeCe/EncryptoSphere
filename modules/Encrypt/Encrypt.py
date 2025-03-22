from abc import ABC, abstractmethod

class Encrypt(ABC):

    def __init__(self, key=None):
        if not key:
            self.key = self.generate_key()
        else:
            self.key = key

    def set_key(self, key) -> None:
        self.key = key

    @abstractmethod
    def generate_key() -> any:
        pass

    @abstractmethod
    def encrypt_file(self, data : bytes) -> bytes:
        pass
    
    @abstractmethod
    def decrypt_file(self, data : bytes) -> bytes:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass
