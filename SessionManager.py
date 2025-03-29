from SharedCloudManager import SharedCloudManager

class SessionManager():
    """
    This class manages shared sessions using the main session and also holds the master key
    """
    def __init__(self, master_key, main_session):
        self.key = master_key
        self.main_session = main_session
        self.sessions = {}

    def get_key(self):
        """
        Returns the master key from the login that was generated
        """
        return self.key
    
    def add_session(self, session : SharedCloudManager):
        """
        Adds a new shared session to the sessions list
        """
        session.authenticate()
        self.sessions[session.root_folder] = session
        session.authenticate()

    def end_session(self, session : SharedCloudManager):
        """
        End a session from the session list if test_session returned false from SharedCloudManager
        """

        try:
            if isinstance(session, str):
                self.sessions.pop(session)
            else:
                self.sessions.pop(session.root_folder)
        except KeyError as e:
            print("No such session exists")
            return

    def sync_new_sessions(self):
        """
        Looks in all clouds for shared sessions
        If one is found, create a SharedCloudManager for the folder and add it to self.sessions using add_session
        """
        new_sessions = {}
        for cloud in self.main_session.clouds:
            shared_folders = cloud.list_shared_folders()
            if shared_folders is None:
                return
            for folder in shared_folders:
                if not SharedCloudManager.is_valid_session_root(cloud, folder):
                    continue
                for session in self.sessions.keys():
                    if session == folder.path:
                        continue
                temp = new_sessions.get(folder.path) if new_sessions.get(folder.path) else []
                temp.append(cloud)
                new_sessions[folder.path] = temp
        for folder,clouds in new_sessions.items():
            self.add_session(SharedCloudManager(None, clouds, folder, self.main_session.split, self.main_session.encrypt))
        self.sync_known_sessions()
                
    def get_session(self, path=None):
        if not path:
            return self.main_session
        return self.sessions.get(path)
        
    def sync_known_sessions(self):
        """
        Goes through all sessions in self.sessions and calls share_keys
        """
        for folder,session in self.sessions.items():
            session.share_keys()


    def check_session_status(self, root=None):
        """
        Goes through session and calls test_access, if the session is inactive, end it
        @param root optional, if given only checks the specific shared session with this root folder if one exists, if None checks all sessions
        @return success, False if at least one session is inactive, True otherwise 
        """
        for folder,session in self.sessions.keys():
            if not session.test_access():
                self.end_session(session)
