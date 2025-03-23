from .Encrypt import Encrypt

class NoEncrypt(Encrypt):
    def __init__(self, key=None):
        super().__init__(key)

    def encrypt_file(self, data):
        return data
    
    def decrypt_file(self, data):
        return data
    
    def get_name(self):
        return "No"
    
    def generate_key(self) -> any:
        return ""