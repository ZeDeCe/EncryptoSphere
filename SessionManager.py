from SharedCloudManager import SharedCloudManager
from CloudManager import CloudManager
from modules.CloudAPI.CloudService import CloudService
from CloudObjects import Directory
import concurrent.futures
from threading import Lock

class SessionManager():
    """
    This class manages shared sessions using the main session and also holds the master key
    """
    def __init__(self, master_key, main_session):
        self.key = master_key
        self.main_session : CloudManager = main_session
        self.sessions : dict[SharedCloudManager] = {}
        self.sessions_lock = Lock()
        self.syncing_sessions = False

    def get_key(self):
        """
        Returns the master key from the login that was generated
        """
        return self.key
    
    def add_session(self, session : SharedCloudManager, session_name=None):
        """
        Adds a new shared session to the sessions list
        """
        status = session.authenticate()
        if not status: # if failed to authenticate for any reason don't show (including pending sessions)
            # we might change this later to show pending sessions as a grayed out folder maybe?
            print(f"Session authentication failed for session {session.root}")
            return
        if session_name is None:
            session_name = session.get_uid()
        with self.sessions_lock:
            self.sessions[session_name] = session

    def end_session(self, session : SharedCloudManager | str):
        """
        End a session from the session list if test_session returned false from SharedCloudManager
        """
        assert isinstance(session, str) or isinstance(session, SharedCloudManager)
        try:
            if isinstance(session, str):
                self.sessions.pop(session)
            elif isinstance(session, SharedCloudManager):
                self.sessions.pop(session.get_uid())
        except KeyError as e:
            print("No such session exists")
            return

    def sync_new_sessions(self):
        """
        Looks in all clouds for shared sessions
        If one is found, create a SharedCloudManager for the folder and add it to self.sessions using add_session
        """
        if self.syncing_sessions:
            return False
        self.syncing_sessions = True

        new_sessions = {}
        for cloud in self.main_session.clouds:
            shared_folders = cloud.list_shared_folders(filter=SharedCloudManager.shared_suffix)
            if shared_folders is None:
                return
            for folder in shared_folders:
                # if not SharedCloudManager.is_valid_session_root(cloud, folder):
                #     continue
                uid = self.__get_shared_folder_uid(cloud, folder)
                if uid is None or uid == "":
                    continue
                id : str = f"{folder.get_name()}${uid}"
                if self.sessions.get(id):
                    continue
                new_sessions[id] = new_sessions.get(id) if new_sessions.get(id) else {}
                new_sessions.get(id)["clouds"] = new_sessions.get(id).get("clouds") if new_sessions.get(id).get("clouds") else []
                new_sessions.get(id)["folders"] = new_sessions.get(id).get("folders") if new_sessions.get(id).get("folders") else {}
                new_sessions.get(id).get("clouds").append(cloud)
                new_sessions.get(id).get("folders")[cloud.get_name()] = folder
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            for id, obj in new_sessions.items():
                name = id.split("$")[0].replace(SharedCloudManager.shared_suffix,"")
                folders = obj.get("folders")
                clouds = obj.get("clouds")
                dir = Directory(folders, "/")
                future = executor.submit(self.add_session,
                    SharedCloudManager(None, dir, clouds, name, self.main_session.split.copy(), self.main_session.encrypt.copy()))
        self.syncing_sessions = False
        self.sync_known_sessions()
        return True
    
    def __get_shared_folder_uid(self, cloud : CloudService, folder : CloudService.Folder) -> str | None:
        files = cloud.list_files(folder, "$UID_")
        for file in files:
            return file.get_name()[5:]
        return None

    def get_session(self, uid=None):
        if not uid:
            return self.main_session
        return self.sessions.get(uid)
        
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
