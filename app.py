"""
This is the app UI 
"""
import customtkinter as ctk
from PIL import Image
from customtkinter import filedialog
import os
from threading import Thread
import tkinter.messagebox as messagebox
import time
import itertools


"""
TODO: For the advanced UI:
      - Add all relevent error/info masseges: EX. "Downloading file...", "Sharing completed" (Advanced UI)
      - Add settings button (template for advanced UI)
      - Add search bar (Advanced UI)
      - OPTIONAL: Add rename option (Advanced UI)
      - Support window resizing (Advanced UI)
      - Add a settings page (Advanced UI)
      More TODOs: At JIRA

"""
class App(ctk.CTk):
    """
    This class creates the UI features and the program main window.
    """
    
    def __init__(self, gateway):
        
        ctk.CTk.__init__(self)
        ctk.set_appearance_mode("dark")
        self.title("EncryptoSphere")

        # As of now we are using specific sizing, on the advanced ui we will need to make dynamic sizing
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry("650x400+%d+%d" % (screen_width/2-325, screen_height/2-200))
        
        # "Backend" functions
        self.api = gateway
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Creating a container for the frames
        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        self.container = container
        # Initializing frames to an empty dictionary
        self.frames = {} 
        self.shared_frames = {}
        # List of all context_menus in the app
        self.context_menus = []
        
        # List of all buttons
        self.buttons = []
        
        # Creating the frames
        for F in (LoginPage, MainPage, SharePage):
            frame = F(container, self)
            self.frames[F] = frame  
            frame.grid(row=0, column=0, sticky="nsew")
        
        # Show the start page (as of this POC, login to the clouds)
        self.show_frame(LoginPage)
        

    def show_frame(self, cont):
        """
        Display the given frame
        @param cont: The frame to be displayed
        """
        if isinstance(cont, SharePageMainPage):
            frame = cont
        elif isinstance(cont, str):
            frame = self.shared_frames[cont]
        else:
            frame = self.frames[cont]
        self.current_frame = frame
        frame.refresh()
        frame.tkraise()

    def get_shared_page(self, path):
        if path in self.shared_frames:
            return self.shared_frames[path]
        frame = SharePageMainPage(self.container, self, path)
        frame.grid(row=0, column=0, sticky="nsew")
        self.shared_frames[path] = frame
        return frame
    
    def get_api(self):
        """
        Get "backend" api's
        """
        return self.api
    
    def on_closing(self):
        """
        Ensure proper cleanup before closing the application
        """    
        self.destroy() 
        if self.api.manager:
            self.api.manager.sync_to_clouds() 
            self.api.manager.delete_fd()
            self.api.manager.stop_sync_thread()
    
    def register_context_menu(self, context_menu):
        """
        Register every new context menu
        This is because we need to close all context menus when clicking on any button in the app.
        @param context_menu: The context menu to be registered
        """
        self.context_menus.append(context_menu)
    
    def button_clicked(self, button, ignore_list):
        """
        When any button is clicked, we need to close all opend context_menu(s)
        @param button: The button that was clicked
        @param ignore_list: List of context menus that should not be closed 
        """
        for menu in self.context_menus:
            if menu not in ignore_list:
                menu.hide_context_menu()

    def change_folder(self, path):
        """
        Change the folder in the main page to the given path
        @param path: The path to the folder to be changed to
        """
        self.current_frame.change_folder(path)
    
    def change_session(self, path):
        """
        Change the session in the main page to the given path
        @param path: The path to the session to be changed to
        """
        self.api.change_session(path)
        

class LoginPage(ctk.CTkFrame):
    """
    This class creates the Login page frame -  Where user enters email and authenticates to the different clouds.
    This class inherits ctk.CTkFrame class.
    """
    def __init__(self, parent, controller):
        ctk.CTkFrame.__init__(self, parent)
        
        self.controller = controller
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5), weight=1)
        
        # Title Label
        label = ctk.CTkLabel(self, text="Welcome to EncryptoSphere ☁︎⋅", 
                             font=("Verdana", 28, "bold"), text_color="white")
        label.grid(row=0, column=0, pady=(60, 20), padx=20, sticky="n")

        # Email Label
        self.message = ctk.CTkLabel(self, text="Enter your Email Address:", font=("Arial", 14), text_color="white")
        self.message.grid(row=1, column=0, padx=20, sticky="w")

        # Email Entry Field
        self.entry = ctk.CTkEntry(self, placeholder_text="example@gmail.com", width=300)
        self.entry.grid(row=2, column=0, padx=20, sticky="ew")

        # Submit Button
        self.submit_button = ctk.CTkButton(self, text="Submit", command=self.__handle_login, width=200, fg_color="#3A7EBF")
        self.submit_button.grid(row=3, column=0, padx=20, pady=(20, 60), sticky="n")
    
    def refresh(self):
        """
        Login page refresh - as of now we dont need this functionality
        """
        pass
    
    def __handle_login(self):
        """
        This function is called when a user hits the submit button after typing the email address.
        The function handles the login process. If successful, it passes control to the MainPage class to display the main page.
        """
        self.submit_button.configure(state="disabled")
        
        # Remove error lable and block the button
        if hasattr(self, 'error_label'):
            self.error_label.grid_forget()
        if hasattr(self, 'retry_button'):
            self.retry_button.configure(state="disabled")
        
        # Load GIF
        self.gif = Image.open("resources/loading-gif.gif")
        self.frames = [ctk.CTkImage(self.gif.copy().convert("RGBA").resize((100, 100)))]

        # Extract all GIF frames
        try:
            while True:
                self.gif.seek(self.gif.tell() + 1)
                self.frames.append(ctk.CTkImage(self.gif.copy().convert("RGBA").resize((100, 100))))
        except EOFError:
            pass

        # Create a label for the GIF and place it under the submit button
        self.gif_label = ctk.CTkLabel(self, image=None, text="")
        self.gif_label.grid(row=4, column=0, pady=(10, 0), sticky="n")

        # Start animation
        self.frame_iterator = itertools.cycle(self.frames)
        self.gif_animation_id = None  # Initialize the animation ID
        Thread(target=self.update_gif()).start()

        email = self.entry.get()
        result = self.controller.get_api().authenticate(email)
        
        if not result:
            self.__show_error("Error While connecting to the Cloud", self.controller.show_frame(LoginPage))
        else:
            # Stop the animation
            if self.gif_animation_id:
                self.after_cancel(self.gif_animation_id)
            self.controller.show_frame(MainPage)
    
    def update_gif(self):
        """
        Loop through frames
        """
        self.gif_label.configure(image=next(self.frame_iterator))
        self.gif_animation_id = self.after(100, self.update_gif)  # Store the after call ID

    def __show_error(self, error_message, func):
        """
        If authentication to the clouds fails, display the error and add retry button.
        Remove the submit button and the GIF.
        """
        # Remove the submit button and GIF
        if hasattr(self, 'submit_button'):
            self.submit_button.grid_forget()
        if hasattr(self, 'gif_label'):
            self.gif_label.grid_forget()
            if self.gif_animation_id:
                self.after_cancel(self.gif_animation_id)

        # Display the error message
        self.error_label = ctk.CTkLabel(self, text=error_message, font=("Arial", 12), text_color="red")
        self.error_label.grid(row=4, column=0, pady=20, sticky="n")

        self.retry_button = ctk.CTkButton(self, text="Retry", command=self.__handle_login, width=200, fg_color="#3A7EBF")
        self.retry_button.grid(row=5, column=0, pady=10, sticky="n")

class MainPage(ctk.CTkFrame):
    """
    This class creates the main page frame -  Where the user can see all the files and folders in the current folder.
    This class inherits ctk.CTkFrame class.
    """
    def __init__(self, parent, controller):
        self.controller = controller

        ctk.CTkFrame.__init__(self, parent)
        self.prev_window = None

        # Create the side bar
        self.side_bar = ctk.CTkFrame(self, fg_color="gray25", corner_radius=0)
        self.side_bar.pack(side=ctk.LEFT, fill="y", expand=False)
        self.side_bar.bind("<Button-1>", lambda e: self.controller.button_clicked(e, []))

        # Add the EncryptoSphere label to the side bar
        self.encryptosphere_label = ctk.CTkLabel(self.side_bar, text="EncryptoSphere", font=("Verdana", 15))
        self.encryptosphere_label.pack(anchor="nw", padx=10, pady=10, expand=False)

        # Create the upload button and shared files button
        self.upload_button = ctk.CTkButton(self.side_bar, text="Upload",
                                           command=lambda: self.open_upload_menu(),
                                           width=120, height=30, fg_color="gray25", hover=False)
        self.upload_button.pack(anchor="nw", padx=10, pady=10, expand=False)

        self.shared_files_button = ctk.CTkButton(self.side_bar, text="Shared Files",
                                                 command=lambda: self.controller.show_frame(SharePage),
                                                 width=120, height=30, fg_color="gray25", hover=False)
        self.shared_files_button.pack(anchor="nw", padx=10, pady=5, expand=False)

        # Bind hover events to the buttons (to change font to bold)
        self.upload_button.bind("<Enter>", lambda e: self.set_bold(self.upload_button))
        self.upload_button.bind("<Leave>", lambda e: self.set_normal(self.upload_button))

        self.shared_files_button.bind("<Enter>", lambda e: self.set_bold(self.shared_files_button))
        self.shared_files_button.bind("<Leave>", lambda e: self.set_normal(self.shared_files_button))

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill = ctk.BOTH, expand = True)
        
        # Create the main frame that will display the files and folders
        root_folder = Folder(self.container, controller, "/")
        self.folders = {"/": root_folder}
        self.main_frame = root_folder
        self.main_frame.pack(fill=ctk.BOTH, expand=True)

        # Create the back button to go back to the previous folder, it is hidden by default (on main page).
        # This button is displayed when the user enters a subfolder.
        self.back_button = ctk.CTkButton(self.side_bar, text="Back ⏎",
                                         command=lambda: self.change_folder(self.get_previous_window(self.main_frame.path)),
                                         width=120, height=30, fg_color="gray25", hover=False)
        self.back_button.pack_forget()

        # Create messages pannel
        self.messages_pannel = ctk.CTkFrame(self.container, fg_color="transparent")
        self.messages_pannel.place(rely=1.0, anchor="sw")
        
        # Create a label that will display current location
        self.curr_path = "/"
        self.url_label = ctk.CTkLabel(self, text=self.curr_path, anchor="e", fg_color="gray30", corner_radius=10)
        self.url_label.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")
        self.bind("<Button-1>", lambda e: self.controller.button_clicked(e, []))

        self.uploading_labels= {}

        self.main_frame.lift()
        self.messages_pannel.lift()


        # Initialize the context menu
        self.initialize_context_menu()

    def initialize_context_menu(self):
        """
        Initialize or recreate the context menu for the upload button.
        """
        self.context_menu = OptionMenu(self, self.controller, [
            {
                "label": "Upload File",
                "color": "gray25",
                "event": lambda: self.upload_file()
            },
            {
                "label": "Upload Folder",
                "color": "gray25",
                "event": lambda: self.upload_folder()
            }
        ])

    def set_bold(self, button):
        """
        Change the button text to bold on hover
        @param button: The button to be changed
        """
        button.configure(font=("Verdana", 13, "bold"))

    def set_normal(self, button):
        """
        Revert the button text to normal when not hovered
        @param button: The button to be changed
        """
        button.configure(font=("Verdana", 13))

    def open_upload_menu(self):
        """
        This function opens the upload menu using the context menu
        """
        print("Upload button clicked")
        if self.context_menu.context_hidden:
            self.controller.button_clicked(self, [self.context_menu])
            self.context_menu.show_context_menu(self.upload_button.winfo_x() + 120, self.upload_button.winfo_y())
        else:
            self.context_menu.hide_context_menu()

    def upload_file(self):
        """
        If upload file option is selected in the upload_context_menu, open file explorer and let the user pick a file
        """
        file_path = filedialog.askopenfilename()
        self.context_menu.hide_context_menu()
        print(file_path)
        if file_path:
            self.upload_file_to_cloud(file_path)

    def upload_file_to_cloud(self, file_path):
        """
        Upload file to the cloud and refresh the page
        @param file_path: The path of the file to be uploaded
        """
        # Create a new label for the uploading file
        self.messages_pannel.lift()
        filename = os.path.basename(file_path)
        uploading_label = ctk.CTkLabel(self.messages_pannel, text=f"Uploading {filename}...", anchor="w", fg_color="gray30", corner_radius=10, padx=10, pady=5)
        uploading_label.pack(side="bottom", pady=2, padx=10, anchor="w")
        uploading_label.lift()  # Ensure the label is on top of all frames

        self.uploading_labels[file_path] = uploading_label

        # Call the API to upload the file and use finish_uploading as the callback
        self.controller.get_api().upload_file(lambda f: self.finish_uploading(file_path), os.path.normpath(file_path), self.main_frame.path)

    def finish_uploading(self, file_path):
        """
        Remove the uploading message for the completed file and reorder the labels
        @param file_path: The path of the file that finished uploading
        """

        if hasattr(self, 'uploading_labels') and file_path in self.uploading_labels:
            # Forget the label for the completed file
            #self.uploading_labels[file_path].pack_forget()
            #del self.uploading_labels[file_path]
            pass
        # Refresh the main frame
        self.main_frame.refresh()

        

    def upload_folder(self):
        """
        If upload folder option is selected in the upload_context_menu, open file explorer and let the user pick a folder
        """
        folder_path = filedialog.askdirectory()
        self.context_menu.hide_context_menu()
        if folder_path:
            self.upload_folder_to_cloud(folder_path) # This function returns immediately

    def upload_folder_to_cloud(self, folder_path):
        """
        Upload folder to the cloud and refresh the page
        @param folder_path: The path of the folder to be uploaded
        """
        self.controller.get_api().upload_folder(lambda f: self.main_frame.refresh(), os.path.normpath(folder_path), self.main_frame.path)
        
    def change_back_button(self, path):
        """
        Change the back button to go back to the previous folder
        @param path: The path to the folder to be changed to
        """
        if path == "/":
            self.back_button.pack_forget()
        else:
            self.back_button.pack(anchor="nw", padx=10, pady=5, expand=False)

    def change_folder(self, path):
        """
        Changes the folder viewed in main_frame
        @param path: The path to the folder to be changed to
        """
        print(f"Current folder: {path}")
        self.change_back_button(path)
        self.main_frame.pack_forget()
        if path in self.folders:
            self.main_frame = self.folders[path]
        else:
            new_folder = Folder(self, self.controller, path)
            self.folders[path] = new_folder
            self.main_frame = new_folder

        self.main_frame.refresh()
        self.main_frame.lift()
        self.messages_pannel.lift()
        if hasattr(self, 'uploading_labels'):
            for label in self.uploading_labels.values():
                label.lift()  # Ensure the label is on top of all frames


        # Reinitialize the context menu when changing folders
        self.initialize_context_menu()

    def refresh(self):
        """
        Refresh the frame and display all updates
        """
        self.main_frame.refresh()
    
    def get_previous_window(self, path):
        """
        Get the previous window (if exists) by given path
        @param path: The path to the current folder
        """
        # Split the path from the right at the last '/'
        parts = path.rsplit('/', 1)
        # If there's only one part or the result is an empty string, return '/'
        if len(parts) == 1 or parts[0] == '':
            return '/'
        # Otherwise, return the first part which is the path without the last segment
        print(parts[0])
        return parts[0]

class Folder(ctk.CTkFrame):
    """
    This class represents the current folder we are in
    It contains all the files and folders that are in the current folder, the current folder, and the frame to display
    """

    def __init__(self, parent, controller : App, path):
        ctk.CTkFrame.__init__(self, parent)
        self.controller = controller
        self.path = path
        self.pack(fill = ctk.BOTH, expand = True)
        self.bind("<Button-1>", lambda e: self.controller.button_clicked(e, []))
        
        self.file_list = {}
        self.folder_list = {}
        
      
    def refresh(self):
        """
        Refresh the frame and display all updates
        """
        file_list, folder_list = self.controller.get_api().get_files(self.path)

        # Add new files to self.file_list
        for file in file_list:
            if file["name"] not in self.file_list:
                self.file_list[file["name"]] = FileButton(self, width=120, height=120, file_data=file, controller=self.controller)

        # Add new folders to self.folder_list
        for folder in folder_list:
            if folder not in self.folder_list:
                self.folder_list[folder] = FolderButton(self, width=120, height=120, folder_path=folder, controller=self.controller)

        self.pack(fill=ctk.BOTH, expand=True)
        columns = 6

        # Forget all existing files and folders
        for widget in self.winfo_children():
            widget.grid_forget()

        for col in range(columns):
            self.grid_columnconfigure(col, weight=1, uniform="file_grid")
        index = 0

        for folder in self.folder_list.values():
            row = index // columns  
            col = index % columns   

            folder.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            index += 1

        for file in self.file_list.values():
            row = index // columns  
            col = index % columns   

            file.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            index += 1
         
        # Create a label that will display current location
        self.url_label = ctk.CTkLabel(self, text=self.path, anchor="e", fg_color="gray30", corner_radius=10)
        self.url_label.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")

class IconButton(ctk.CTkFrame):
    """
    This class is an abstract button class for all icons that go in MainFrame
    """
    def __init__(self, master, width, height, icon_path, text, controller):
        ctk.CTkFrame.__init__(self, master, width=width, height=height)
        self.controller = controller
        self.master = master
        self.file_icon = ctk.CTkImage(light_image=Image.open(icon_path), size=(40, 40))

        icon_label = ctk.CTkLabel(self, image=self.file_icon, text="")
        icon_label.pack(pady=(5, 0))

        name_label = ctk.CTkLabel(self, text=text, font=("Arial", 9), wraplength=90, justify="center")
        name_label.pack(pady=(0, 5))

        # Connect all file related content to do the same action when clicked (open the context_menu)
        self.bind("<Button-1>", lambda e: self.on_button1_click(e), add="+")
        icon_label.bind("<Button-1>", lambda e: self.on_button1_click(e), add="+")
        name_label.bind("<Button-1>", lambda e: self.on_button1_click(e), add="+")
        self.bind("<Button-3>", lambda e: self.on_button3_click(e), add="+")
        icon_label.bind("<Button-3>", lambda e: self.on_button3_click(e), add="+")
        name_label.bind("<Button-3>", lambda e: self.on_button3_click(e), add="+")
        self.bind("<Double-Button-1>", lambda e: self.on_double_click(e), add="+")
        icon_label.bind("<Double-Button-1>", lambda e: self.on_double_click(e), add="+")
        name_label.bind("<Double-Button-1>", lambda e: self.on_double_click(e), add="+")
    
    def on_button1_click(self, event=None):
        pass

    def on_double_click(self, event=None):
        pass
    
    def on_button3_click(self, event=None):
        pass

class FileButton(IconButton):
    """
    This class represents a "file button"
    A file button is the frame surronding the file icon and name, so every mouse click in that area is considered as an action related to that specific file 
    """
    def __init__(self, master, width, height, file_data, controller):
        IconButton.__init__(self, master, width, height, "resources/file_icon.png", file_data["name"], controller)
        self.file_data = file_data
        print(self.file_data)
        print(self.file_data["name"])
        print(self.file_data["id"])

        # Create a context menu using CTkFrame for file operations (As of now we have only download and delete)
        self.context_menu = OptionMenu(master.master.master, self.controller, [
            {
                "label": "Download File",
                "color": "blue",
                "event": lambda: Thread(target=self.download_file_from_cloud, args=(self.file_data,), daemon=True).start()
             },
             {
                 "label": "Delete File",
                 "color": "red",
                 "event": lambda: Thread(target=self.delete_file_from_cloud, args=(self.file_data,), daemon=True).start()
             }
        ])

        self.controller.register_context_menu(self.context_menu)

    def download_file_from_cloud(self, file_data):
        """
        Download file from the cloud and refresh the page
        @param file_id: The id of the file to be downloaded
        """
        self.controller.get_api().download_file(None, file_data["id"])


    def delete_file_from_cloud(self, file_data):
        """
        Delete file from the cloud and refresh the page
        @param file_id: The id of the file to be deleted
        """
        self.controller.get_api().delete_file(lambda f: self.master.master.master.refresh(), file_data["id"])
        del self.master.file_list[file_data["name"]]

    def on_button1_click(self, event=None):
        """
        When clicking on a file, open the context menu for that file, double clicking means open-close the context menu
        Click on a file close any other open context menus
        @param event: The event that triggered this function
        """
        self.controller.button_clicked(self, [self.context_menu])
        if self.context_menu.context_hidden:
            self.context_menu.lift()
            self.context_menu.show_context_menu(event.x_root - self.master.winfo_rootx(), event.y_root - self.master.winfo_rooty())
        else:
           self.context_menu.hide_context_menu()
              
class OptionMenu(ctk.CTkFrame):
    """
    Class to create the context menu option bar
    """
    def __init__(self, master, controller, buttons):
        """
        @param buttons list of dictionaries as such: [{"label" : str, "color": str, "event": function}]
        """
        ctk.CTkFrame.__init__(self, master, corner_radius=5, fg_color="gray25")
        self.controller = controller
        self.context_hidden = True
        self.buttons = []
        
        for button in buttons:
            butt = ctk.CTkButton(self, text=button["label"],
                                      command=button["event"],
                                      width=120, height=30, fg_color=button["color"])
            butt.pack(pady=5, padx=10)
            butt.bind("<Button-1>", lambda event: self.hide_context_menu(), add="+")
            self.buttons.append(butt)

        self.controller.register_context_menu(self)

    def hide_context_menu(self):
        """
        Hide the current context menu
        """
        if not self.context_hidden:
            self.context_hidden = True
            self.place_forget()
        
    def show_context_menu(self, x, y):
        """
        Display the current context menu on the selected location
        """
        self.context_hidden = False
        self.place(x=x, y=y)

class FolderButton(IconButton):
    """
    This class represents a "folder button"
    A folder button is the frame surronding the folder icon and name, so every mouse click in that area is considered as an action related to that specific folder
    """
    def __init__(self, master, width, height, folder_path, controller):
        self.folder_path = folder_path
        name_index = folder_path.rfind("/")+1
        if len(folder_path) > name_index:
            self.folder_name = folder_path[name_index:]
        elif folder_path == "/":
            self.folder_name = "/"
        else:
            raise Exception("Invalid folder path")  
        
        IconButton.__init__(self, master, width, height, "resources/folder_icon.png", self.folder_name, controller)
        self.controller = controller
        self.master = master

        # Create a context menu using CTkFrame for folder operations (As of now we don't suport these operations)
        self.context_menu = OptionMenu(master.master.master, self.controller, [
            {
                "label": "Download Folder",
                "color": "blue",
                "event": lambda: self.download_folder()
             },
             {
                 "label": "Delete Folder",
                 "color": "red",
                 "event": lambda: self.delete_folder() # maybe add "ARE YOU SURE?"
             }
        ])
        self.controller.register_context_menu(self.context_menu)
    
    
    def delete_folder(self):
        """
        Delete folder from the cloud and refresh the page
        @param folder_path: The path of the folder to be deleted
        """
        # The callback here might need to just check that it didn't fail and we should instead delete the folder immediately
        self.controller.get_api().delete_folder(lambda f: self.master.master.master.refresh(), self.folder_path)
    
    
    def download_folder(self):
        """
        Download folder from the cloud and refresh the page
        @param folder_path: The path of the folder to be downloaded
        """
        # Can add a callback to notify user that the download is complete
        self.controller.get_api().download_folder(None, self.folder_path)

    def on_double_click(self, event=None):
        """
        When double clicking on a folder, Display the folder contents
        @param event: The event that triggered this function
        """
        self.controller.change_folder(self.folder_path)
    
    def on_button3_click(self, event=None):
        if self.context_menu.context_hidden:
            self.context_menu.lift()
            self.context_menu.show_context_menu(event.x_root - self.master.master.winfo_rootx(), event.y_root - self.master.master.master.winfo_rooty())
        else:
            self.context_menu.hide_context_menu()

class SharePageMainPage(MainPage):
    def __init__(self, parent, controller, path):
        self.path = path
        super().__init__(parent, controller)
        self.back_button.pack(anchor="nw", padx=10, pady=5, expand=False)
        self.back_button.configure(command=lambda: self.controller.show_frame(SharePage) if self.main_frame.path == "/" else self.change_folder(self.get_previous_window(self.main_frame.path)))
        self.shared_files_button.pack_forget()
        parsed_path = path.replace("_ENCRYPTOSPHERE_SHARE", "")
        parsed_path = parsed_path.split("/")[-1]
        self.encryptosphere_label.configure(text=parsed_path)

    def change_folder(self, path):
        """
        Changes the folder viewed in main_frame
        @param path: The path to the folder to be changed to
        """
        print(f"Current folder: {path}")

        self.main_frame.pack_forget()
        if path in self.folders:
            self.main_frame = self.folders[path]
        else:
            new_folder = Folder(self, self.controller, path)
            self.folders[path] = new_folder
            self.main_frame = new_folder

        self.main_frame.refresh()
        self.main_frame.lift()

        # Reinitialize the context menu when changing folders
        self.initialize_context_menu()




class SharePage(ctk.CTkFrame):
    """
    This class creates the share page frame -  Where the user can share folders with other users and view shared folders.
    This class inherits ctk.CTkFrame class.
    """
    def __init__(self, parent, controller):
        
        self.controller = controller
        ctk.CTkFrame.__init__(self, parent)

        # Create the side bar
        self.side_bar = ctk.CTkFrame(self, fg_color="gray25", corner_radius=0)
        self.side_bar.pack(side = ctk.LEFT,fill="y", expand = False)

        # Add the EncryptoSphere label to the side bar
        encryptosphere_label = ctk.CTkLabel(self.side_bar, text="Shared Folders", font=("Verdana", 15))
        encryptosphere_label.pack(anchor="nw", padx=10, pady=10, expand = False)

        # Create the upload button and create share buttons
        self.share_folder_button = ctk.CTkButton(self.side_bar, text="New Share",
                                      command=lambda: self.open_sharing_window(),
                                      width=120, height=30, fg_color="gray25", hover=False)
        self.share_folder_button.pack(anchor="nw", padx=10, pady=5, expand = False)

        self.share_folder_button.bind("<Enter>", lambda e: self.set_bold(self.share_folder_button))
        self.share_folder_button.bind("<Leave>", lambda e: self.set_normal(self.share_folder_button))
        self.back_button = ctk.CTkButton(self.side_bar, text="Back ⏎",
                                                 command=lambda: self.back_to_main_window(),
                                                 width=120, height=30, fg_color="gray25", hover=False)
        self.back_button.pack(anchor="nw", padx=10, pady=10, expand=False)

        self.back_button.bind("<Enter>", lambda e: self.set_bold(self.back_button))
        self.back_button.bind("<Leave>", lambda e: self.set_normal(self.back_button))


        
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.pack(fill = ctk.BOTH, expand = True)

        self.shared_folder_list = {}


    def set_bold(self, button):
        """
        Change the button text to bold on hover
        @param button: The button to be changed
        """
        button.configure(font=("Verdana", 13, "bold"))

    def set_normal(self, button):
        """
        Revert the button text to normal when not hovered
        @param button: The button to be changed
        """
        button.configure(font=("Verdana", 13))
    
    def back_to_main_window(self):
        """
        This function is called when the user clicks the back button to return to the main page
        """
        self.controller.get_api().change_session()
        self.controller.show_frame(MainPage)

    def open_sharing_window(self):
        """
        This function opens the upload menu with inputs for folder name and email list

        TODO: Add an option to select clouds to share with and for each member to select different email for each cloud

        """ 
        new_window = ctk.CTkToplevel(self)
        new_window.title("New Share")
        # Bring to front & keep it on top of the main window
        new_window.lift()  
        new_window.transient(self)  

        # Get the position and size of the parent (controller) window
        main_x = self.controller.winfo_x()
        main_y = self.controller.winfo_y()
        main_w = self.controller.winfo_width()
        main_h = self.controller.winfo_height()
        # Size of the new window
        # TODO: dynamic sizing
        new_w, new_h = 400, 350  

        # Calculate the position to center the new window over the parent window
        new_x = main_x + (main_w // 2) - (new_w // 2)
        new_y = main_y + (main_h // 2) - (new_h // 2)
        new_window.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")

        # Create a frame for the scrollable area
        frame = ctk.CTkFrame(new_window)
        frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        # Create a scrollable frame inside the main frame
        scrollable_frame = ctk.CTkScrollableFrame(frame)
        scrollable_frame.pack(fill=ctk.BOTH, expand=True)

        # Folder name input (label above the entry field)
        folder_label = ctk.CTkLabel(scrollable_frame, text="Enter Folder Name:", anchor="w")
        folder_label.grid(row=0, column=0, padx=(0, 10), pady=(20, 5), sticky="w")
        folder_name_entry = ctk.CTkEntry(scrollable_frame, width=200)
        folder_name_entry.grid(row=1, column=0, pady=5, sticky="w")

        # Share with header
        share_with_label = ctk.CTkLabel(scrollable_frame, text="Share with:", anchor="w")
        share_with_label.grid(row=2, column=0, padx=(0, 10), pady=(20, 5), sticky="w")
        
        # Email list input
        email_frame = ctk.CTkFrame(scrollable_frame, fg_color=scrollable_frame.cget('fg_color'))  # Match background
        email_frame.grid(row=3, column=0, columnspan=2, pady=0, sticky="w")

        # List to hold email input fields
        email_inputs = []  

        # Initial email input field
        initial_email_entry = ctk.CTkEntry(email_frame, width=200)
        initial_email_entry.grid(row=1, column=0, pady=5, padx=(0, 10), sticky="w")
        email_inputs.append(initial_email_entry)

        # Function to add new email input
        def add_email_input():
            if len(email_inputs) < 5:
                new_email_entry = ctk.CTkEntry(email_frame, width=200)
                new_email_entry.grid(row=len(email_inputs) + 1, column=0, pady=5, padx=(0, 10), sticky="w")
                email_inputs.append(new_email_entry)

        # "+" button to add email inputs (styled as a small circular button)
        plus_button = ctk.CTkButton(email_frame, text="+", command=add_email_input, width=30, height=30, corner_radius=15)
        plus_button.grid(row=1, column=1, padx=10, pady=5)

        # Function to handle the creation of new share
        def create_new_share():
            folder_name = folder_name_entry.get()
            emails = [email.get() for email in email_inputs]
            print(f"Creating share with folder: {folder_name} and emails: {emails}")
            # Call a new function with the folder and emails (replace this with your logic)
            self.controller.get_api().create_shared_session(lambda f: self.refresh(), folder_name, emails)
            # Close the new window
            new_window.destroy()

        # Create new share button (this now does both actions: create share and close the window)
        create_share_button = ctk.CTkButton(scrollable_frame, text="Create New Share", command=create_new_share)
        create_share_button.grid(row=100, column=0, pady=50, padx=100, sticky="s")

        # Adjust the scrollbar to make it thinner (no slider_length argument)
        new_window.after(100, lambda: scrollable_frame._scrollbar.configure(width=8))  # Adjust the width of the scrollbar
    

    
    def refresh(self):
        """
        Refresh the frame and display all updates
        """
        folder_list = self.controller.get_api().get_shared_folders()
        
        for folder in folder_list:
            if folder not in self.shared_folder_list:
                self.shared_folder_list[folder] = SharedFolderButton(self.main_frame, width=120, height=120, folder_name=folder, controller=self.controller)

        columns = 6
        cell_size = 120

        for widget in self.main_frame.winfo_children():
            widget.grid_forget()
        

        for col in range(columns):
            self.main_frame.grid_columnconfigure(col, weight=1, uniform="file_grid")

        index = 0
        for folder in self.shared_folder_list.values():
            row = index // columns  
            col = index % columns   
            folder.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            index +=1
        





class SharedFolderButton(IconButton):
    """
    This class represents a "shared folder button"
    A shared folder button is the frame surronding the folder icon and name, so every mouse click in that area is considered as an action related to that specific folder 
    """
    
    def __init__(self, master, width, height, folder_name, controller):

        
        # Get the folder name from the path
        self.full_folder_name = folder_name
        folder_name = folder_name.replace("_ENCRYPTOSPHERE_SHARE", "")
        folder_name = folder_name.split("/")[-1]

        super().__init__(master, width, height, "resources/folder_icon.png", folder_name, controller)
        self.controller = controller
        self.master = master
        self.folder_name = folder_name
        

        # Create a context menu using CTkFrame (for shared folder operations (As of now we don't suport these operations)
        self.context_menu = OptionMenu(master.master.master, self.controller, [
            {
                "label": "Add Member",
                "color": "green4",
                "event": lambda: Thread(target=self.add_member_on_shared_folder, args=(), daemon=True).start() #TODO: add the function to add member
             },
             {
                 "label": "Remove member",
                 "color": "green4",
                 "event": lambda: Thread(target=self.remove_member_from_shared_folder, args=(), daemon=True).start()
             },
                         {
                "label": "Leave Share",
                "color": "red",
                "event": lambda: Thread(target=self.leave_shared_folder, args=(), daemon=True).start()
             },
             {
                 "label": "Delete Share",
                 "color": "red",
                 "event": lambda: Thread(target=self.delete_shared_folder, args=(), daemon=True).start()
             }
        ])

        self.controller.register_context_menu(self.context_menu)

    def on_double_click(self, event=None):
        """
        When double clicking on a folder, Display the folder contents
        @param event: The event that triggered this function
        """
        # Add here the correct function
        self.controller.change_session(self.full_folder_name)
        self.controller.show_frame(self.controller.get_shared_page(self.full_folder_name))

        
    def add_member_on_shared_folder(self):
        pass

    def remove_member_from_shared_folder(self):
        pass

    def leave_shared_folder(self):
        pass

    def delete_shared_folder(self):
        pass

    def on_button3_click(self, event=None):
        """
        When clicking on a file, open the context menu for that file, double clicking means open-close the context menu
        Click on a file close any other open context menu
        @param event: The event that triggered this function
        """
        self.controller.button_clicked(self, [self.context_menu])
        if self.context_menu.context_hidden:
            self.context_menu.lift()
            self.context_menu.show_context_menu(event.x_root - self.master.winfo_rootx(), event.y_root - self.master.winfo_rooty())
        else:
           self.context_menu.hide_context_menu()