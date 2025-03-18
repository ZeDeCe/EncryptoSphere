import FileDescriptor as FileDescriptor
import CloudAbstraction

class SessionManager:
    def __init__(self, key):
        self.current_sessions = []
    
    def add_session(self, key, cloud_manager):
        self.current_sessions.append(Session(key, cloud_manager))
    
    def add_shared_session(self, key):
        pass

class Session:
    def __init__(self, key : str, cloud_manager : CloudAbstraction):
        self.key = key
        self.manager = cloud_manager
    
