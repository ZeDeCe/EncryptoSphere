from SharedCloudManager import SharedCloudManager
from CloudManager import CloudManager
from modules.CloudAPI.CloudService import CloudService
from CloudObjects import Directory
import concurrent.futures
from threading import Lock
import concurrent.futures as futures

class SessionManager():
    """
    This class manages shared sessions using the main session and also holds the master key
    """
    def __init__(self, main_session):
        self.main_session : CloudManager = main_session
        self.sessions : dict[str, SharedCloudManager] = {}
        self.sessions_lock = Lock()
        self.syncing_sessions = False
        self.sessions_ready = False
        self.pending_folders: dict[str, SharedCloudManager] = {}

 
    def shared_sessions_ready(self):
        """
        Returns True if the sessions are ready to be used, False otherwise
        """
        return self.sessions_ready
    
    def add_session(self, session: SharedCloudManager, session_name=None):
        """
        Adds a new shared session to the sessions list.
        If authentication fails, add the session to the pending folders list.
        """
        status = session.authenticate()
        if session_name is None:
            session_name = session.get_uid()
        if not status:  # If failed to authenticate, add to pending folders
            print(f"Session {session.root} is not yet authenticated.")
            if session not in self.pending_folders:
                with self.sessions_lock:
                    self.pending_folders[session_name] = session
            return

        # If the session is authenticated, remove it from pending folders
        if self.pending_folders.get(session_name):
            with self.sessions_lock:
                self.pending_folders.pop(session_name)

        with self.sessions_lock:
            self.sessions[session_name] = session

    def end_session(self, session: SharedCloudManager | str):
        """
        End a session from the session list by calling delete_session in SharedCloudManager.
        """
        assert isinstance(session, str) or isinstance(session, SharedCloudManager)
        try:
            pending = False
            sess = session
            if isinstance(session, str):
                sess = self.sessions.get(session, self.pending_folders.get(session, None))
                if not sess:
                    raise KeyError(f"No such session '{session}' exists.")
            sess.delete_session()  # Call delete_session in SharedCloudManager
            if self.sessions.get(sess.get_uid()):
                self.sessions.pop(sess.get_uid(), None)
            else:
                self.pending_folders.pop(sess.get_uid(), None)
            print(f"Session '{sess.get_uid()}' ended successfully.")
        except KeyError as e:
            print(f"No such session exists: {e}")
        except Exception as e:
            print(f"Error ending session: {e}")

    def sync_new_sessions(self):
        """
        Looks in all clouds for shared sessions
        If one is found, create a SharedCloudManager for the folder and add it to self.sessions using add_session
        """
        try:
            if self.syncing_sessions:
                return False
            self.syncing_sessions = True
            if self.sessions_ready:
                with futures.ThreadPoolExecutor(max_workers=1) as executor:
                    fut = executor.submit(self.sync_known_sessions)
                    def handle_done(f):
                        if f.exception() is not None:
                            print(f"Error syncing known sessions: {f.exception()}")
                        else:
                            print("Successfully synced known sessions")
                    fut.add_done_callback(handle_done)

            new_sessions = {}
            def add_folder_uid(cloud, folder):
                uid = self.__get_shared_folder_uid(cloud, folder)
                if uid is None or uid == "":
                    return None, None
                id : str = f"{folder.get_name().replace(SharedCloudManager.shared_suffix, '')}${uid}"
                if self.sessions.get(id):
                    return None, None
                return folder, id
            shared_folders_iterables = {}
            for cloud in self.main_session.clouds:
                shared_folders = cloud.list_shared_folders(filter=SharedCloudManager.shared_suffix)
                if shared_folders is None:
                    continue
                shared_folders_iterables[cloud] = shared_folders

            for cloud, shared_folders in shared_folders_iterables.items():
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    for folder, id in executor.map(lambda folder, cloud=cloud: add_folder_uid(cloud, folder), shared_folders):
                        if folder is None or id is None:
                            continue
                        new_sessions[id] = new_sessions.get(id) if new_sessions.get(id) else {}
                        new_sessions.get(id)["clouds"] = new_sessions.get(id).get("clouds") if new_sessions.get(id).get("clouds") else []
                        new_sessions.get(id)["folders"] = new_sessions.get(id).get("folders") if new_sessions.get(id).get("folders") else {}
                        new_sessions.get(id).get("clouds").append(cloud)
                        new_sessions.get(id).get("folders")[cloud.get_name()] = folder

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                for id, obj in new_sessions.items():
                    name = id.split("$")[0].replace(SharedCloudManager.shared_suffix,"")
                    folders = obj.get("folders")
                    clouds = obj.get("clouds")
                    dir = Directory(folders, "/")
                    future = executor.submit(self.add_session,
                        SharedCloudManager(None, dir, clouds, name, self.main_session.split.copy(), self.main_session.encrypt.copy()))
                    future.add_done_callback(lambda f: print(f.exception()) if f.exception() is not None else print(f"Added session {name} successfully"))
            self.sessions_ready = True
            print(f"Finished syncing new sessions, found {len(new_sessions)} new sessions")
            return True
        except Exception as e:
            print(f"Error syncing new sessions: {e}")
            self.syncing_sessions = False
            return False
        finally:
            self.syncing_sessions = False
    
    def is_sessions_ready(self):
        """
        Returns True if the sessions are ready to be used, False otherwise
        """
        return self.sessions_ready

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
        to_end = []
        for folder,session in self.sessions.items():
            if not session.test_access():
                print(f"Session {session.get_uid()} is inactive, ending it.")
                if not session.is_owner:
                    to_end.append(session)
                else:
                    print(f"Session {session.get_uid()} is inactive but is the owner, not ending it.")
                    # We should technically gray out the session in the UI since we can't access it but should not attempt to delete it
            else:
                session.share_keys()
        for folder, session in self.pending_folders.items():
            if not session.test_access():
                to_end.append(session)

        for session in to_end:
            self.end_session(session)


    def check_session_status(self, root=None):
        """
        Goes through session and calls test_access, if the session is inactive, end it
        @param root optional, if given only checks the specific shared session with this root folder if one exists, if None checks all sessions
        @return success, False if at least one session is inactive, True otherwise 
        """
        for folder,session in self.sessions.keys():
            if not session.test_access():
                self.end_session(session)
