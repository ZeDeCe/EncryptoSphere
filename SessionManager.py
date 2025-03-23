from CloudManager import CloudManager

class SessionManager():
    """
    This class manages shared sessions using the main session and also holds the master key
    """
    def __init__(self, master_key, main_session):
        self.key = master_key
        self.main_session = main_session
        self.sessions = []

    def get_key(self):
        """
        Returns the master key from the login that was generated
        """
        return self.key
    
    def add_session(self, session : CloudManager):
        """
        Adds a new shared session to the sessions list
        """
        pass

    def end_session(self):
        """
        End a session from the session list
        """
        pass

    def sync_new_sessions(self):
        """
        Looks in all clouds for newly shared sessions
        If one is found, create private,public key pair and upload public key + TFEK to folder
        """
        pass

    def sync_known_sessions(self):
        """
        Looks in known sessions for updates
        1. If another user's public key is found and our FEK exists, use the public key to share the session key with the new user
        2. If we shared a session key, look if we got the shared key and create a new session
        """
        pass