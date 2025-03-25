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
        self.sessions.append(session)

    def end_session(self):
        """
        End a session from the session list if test_session returned false from SharedCloudManager
        """
        pass

    def sync_new_sessions(self):
        """
        Looks in all clouds for shared sessions
        If one is found, create a SharedCloudManager for the folder and add it to self.sessions using add_session
        """
        pass

    def sync_known_sessions(self):
        """
        Goes through all sessions in self.sessions and calls share_keys
        """
        pass

    def check_session_status(self, root=None):
        """
        Goes through session and calls test_access, if the session is inactive, end it
        @param root optional, if given only checks the specific shared session with this root folder if one exists, if None checks all sessions
        @return success, False if at least one session is inactive, True otherwise 
        """