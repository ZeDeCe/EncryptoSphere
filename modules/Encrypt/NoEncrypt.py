from .Encrypt import Encrypt

class NoEncrypt(Encrypt):
    def encrypt_file(self, data):
        return data
    
    def decrypt_file(self, data):
        return data