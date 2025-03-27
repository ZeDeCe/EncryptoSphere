from abc import ABC, abstractmethod

class Encrypt(ABC):
    @staticmethod
    def get_class(sig):
        for cls in Encrypt.__subclasses__():
            if cls.get_name() == sig:
                return cls
                
    def __init__(self, key=None):
        if not key:
            self.key = self.generate_key()
        else:
            self.key = key

    def set_key(self, key) -> None:
        self.key = key

    def get_key(self) -> bytes:
        return self.key
    
    @abstractmethod
    def generate_key() -> bytes:
        pass

    @abstractmethod
    def encrypt(self, data : bytes) -> bytes:
        pass
    
    @abstractmethod
    def decrypt(self, data : bytes) -> bytes:
        pass

    
    @staticmethod
    @abstractmethod
    def get_name() -> str:
        pass
