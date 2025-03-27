from .Encrypt import Encrypt

class NoEncrypt(Encrypt):
    def __init__(self, key=None):
        super().__init__(key)

    def encrypt(self, data):
        return data
    
    def decrypt(self, data):
        return data
    
    @staticmethod
    def get_name():
        return "No"
    
    def generate_key(self) -> bytes:
        return b"NOKEY"