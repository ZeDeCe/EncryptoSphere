import modules.FileDescriptor as FileDescriptor

class SessionManager:
    def __init__(self, key):
        self.current_sessions = []
    
    def add_session(self, key):
        self.current_sessions.append(Session(key))
    
    def add_shared_session(self, key):
        pass

class Session:
    def __init__(self, key):
        self.key = key
    
    def set_key(self, new_key):
        self.key = new_key
    
    def get_key(self):
        return self.key
    
