from abc import ABC, abstractmethod

class Encrypt(ABC):
    @abstractmethod
    def encrypt_file(self, data):
        pass
    
    @abstractmethod
    def decrypt_file(self, data):
        pass