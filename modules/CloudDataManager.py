import keyring
from cryptography.fernet import Fernet
from pathlib import Path
import json

APP_NAME = "EncryptoSphereApp"

class CloudDataManager:
    """
    A class to manage a single cloud service's data that is relevant locally such as the refresh OAuth token
    """
    def __init__(self, app_name: str, cloud_name : str):
        self.app_name = APP_NAME
        self.key_name = cloud_name
        self.file = Path("clouddata", f".{cloud_name}_data")
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.touch(exist_ok=True)
        # Load or create encryption key
        key = keyring.get_password(app_name, self.key_name)
        if key is None:
            key = Fernet.generate_key().decode()
            keyring.set_password(app_name, self.key_name, key)

        self.fernet = Fernet(key.encode())
    
    def set_data(self, data: dict | list) -> None:
        encrypted = self.fernet.encrypt(json.dumps(data).encode())
        self.file.write_bytes(encrypted)

    def get_data(self, key=None) -> dict | list:
        encrypted = self.file.read_bytes()
        data = None
        try:
            data = json.loads(self.fernet.decrypt(encrypted).decode())
        except Exception as e:
            return None

        if key is not None and isinstance(data, dict):
            return data.get(key, None)
        if key is not None and isinstance(data, list):
            return data[key] if key < len(data) else None
        return data
    
    def add_data(self, data: dict) -> None:
        current_data = self.get_data()
        if current_data:
            current_data.update(data)
        else:
            current_data = data
        self.set_data(current_data)
            