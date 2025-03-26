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

"""
TODO: - Add all relevent error/info masseges (Advanced UI)
      - Add settings button (template for advanced UI)
      - Handle folders (?)
      - Add shares button and share Class (frame)
      - Add search bar (Advanced UI)
      - OPTIONAL: Add rename option (Advanced UI)
"""
class App(ctk.CTk):
    """
    This class creates the UI features and the program main window.
    """
    
    def __init__(self, gateway):
        
        ctk.CTk.__init__(self)
        self.title("EncryptoSphere")

        # As of now we are using specific sizing, on the advanced ui we will need to make dynamic sizing
        self.geometry("650x400")
        
        # "Backend" functions
        self.api = gateway
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Creating a container for the frames
        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        # Initializing frames to an empty dictionary
        self.frames = {} 

        # List of all context_menus in the app
        self.context_menus = []
        
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
        """
        frame = self.frames[cont]
        frame.refresh()
        frame.tkraise()

    def get_api(self):
        """
        Get "backend" api's
        """
        return self.api
    
    def on_closing(self):
        """Ensure proper cleanup before closing the application."""
        self.api.manager.sync_to_clouds()
        if messagebox.askokcancel("Quit", "Are you sure you want to exit?"):
            self.api.manager.stop_sync_thread()
            time.sleep(1)
            self.destroy()  # Close the window properly
    
    def register_context_menu(self, context_menu):
        """
        Register every new context menu
        """
        self.context_menus.append(context_menu)
    
    def button_clicked(self, button, ignore_list):
        """
        When any button is clicked, we need to close all opend context_menu(s)
        """
        for menu in self.context_menus:
            if menu not in ignore_list:
                menu.hide_context_menu()

class LoginPage(ctk.CTkFrame):
    """
    This class creates the Login page frame -  Where user enters email and authenticates to the different clouds.
    This class inherits ctk.CTkFrame class.
    TODO: Design this page better.
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
        Login page refresh - as of now we donr need this functionality
        """
        pass
    
    def __handle_login(self):
        """
        This function is called when a user hit the submit button after typing the email address
        The function hendels the login process, if succedded it pass the control to tne MainPage class - to display the main page
        """
        email = self.entry.get()
        result = self.controller.get_api().authenticate(email)
        
        if not result:
            self.__show_error("Error While connecting to the Cloud", self.controller.show_frame(LoginPage))
        else:
            self.controller.show_frame(MainPage)
    
    def __show_error(self, error_message, func):
        """
        If authentication to the clouds fails, display the error and add retry button
        """
        self.error_label = ctk.CTkLabel(self, text=error_message)
        self.error_label.grid(row=4, column=0, pady=20, sticky="n")
        
        self.retry_button = ctk.CTkButton(self, text="Retry", command=func)
        self.retry_button.grid(row=5, column=0, pady=10, sticky="n")

class MainPage(ctk.CTkFrame):
    """
    This class creates the Main page frame after successful login.
    This class inherits ctk.CTkFrame class.
    """
    def __init__(self, parent, controller):
        
        self.controller = controller

        ctk.CTkFrame.__init__(self, parent)

        
        self.side_bar = ctk.CTkFrame(self, fg_color="gray25", corner_radius=0)
        self.side_bar.pack(side = ctk.LEFT,fill="y", expand = False)

        encryptosphere_label = ctk.CTkLabel(self.side_bar, text="EncryptoSphere", font=("Verdana", 15))
        encryptosphere_label.pack(anchor="nw", padx=10, pady=10, expand = False)

        self.upload_button = ctk.CTkButton(self.side_bar, text="Upload",
                                      command=lambda: self.open_upload_menu(),
                                      width=120, height=30, fg_color="gray25", hover=False)
        self.upload_button.pack(anchor="nw", padx=10, pady=10, expand = False)

        self.shared_files_button = ctk.CTkButton(self.side_bar, text="Shared Files",
                                                 command=lambda: self.controller.show_frame(SharePage),
                                                 width=120, height=30, fg_color="gray25", hover=False)
        self.shared_files_button.pack(anchor="nw", padx=10, pady=5, expand=False)

        self.upload_button.bind("<Enter>", lambda e: self.set_bold(self.upload_button))
        self.upload_button.bind("<Leave>", lambda e: self.set_normal(self.upload_button))

        self.shared_files_button.bind("<Enter>", lambda e: self.set_bold(self.shared_files_button))
        self.shared_files_button.bind("<Leave>", lambda e: self.set_normal(self.shared_files_button))
        
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.pack(fill = ctk.BOTH, expand = True)

        # Context_menu object for the upload button (offers 2 options - upload file or upload folder)
        # This is because windows os filesystem cannot open the explorer to select file and folder at the same time.
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
        """ Change the button text to bold on hover. """
        button.configure(font=("Verdana", 13, "bold"))

    def set_normal(self, button):
        """ Revert the button text to normal when not hovered. """
        button.configure(font=("Verdana", 13))
        
    def open_upload_menu(self):
        """
        This function opens the upload menu using the context_menue.
        """ 
        if self.context_menu.context_hidden:
            self.controller.button_clicked(self, [self.context_menu])
            self.context_menu.show_context_menu(self.upload_button.winfo_x()+(120), self.upload_button.winfo_y())
        else:
            self.context_menu.hide_context_menu()

    def upload_file(self):
        """
        If upload file option is selected in the upload_context_menu, open file explorer and let the user pick a file.
        In a new thread, call upload_file_to_cloud to upload the file to the clouds and. After a successful upload, refresh the frame so a the new file will be displayed
        TODO: Add test to see if the upload was succesful, if so - resresh the frame. Else pop an error message!
        """
        file_path = filedialog.askopenfilename()
        self.context_menu.hide_context_menu()
        print(file_path)
        if file_path:
            Thread(target=self.upload_file_to_cloud, args=(file_path,), daemon=True).start()
            

    def upload_file_to_cloud(self, file_path):
        """
        Upload file to the cloud and refresh the page
        """
        self.controller.get_api().upload_file(os.path.normpath(file_path))
        self.refresh()


    def upload_folder(self):
        """
        If upload folder option is selected in the upload_context_menu, open file explorer and let the user pick a folder.
        In a new thread, call upload_folder_to_cloud to upload the folder to the clouds. After a successful upload, refresh the frame so a the new folder will be displayed
        TODO: Add test to see if the upload was succesful, if so - resresh the frame. Else pop an error message!
        """
        folder_path = filedialog.askdirectory()
        self.context_menu.hide_context_menu()
        if folder_path:
            Thread(target=self.upload_folder_to_cloud, args=(folder_path,), daemon=True).start()
        
    def upload_folder_to_cloud(self, folder_path):
        """
        Upload folder to the cloud and refresh the page
        """
        self.controller.get_api().upload_folder(os.path.normpath(folder_path))
        self.refresh()
    
    def refresh(self):
        """
        Refresh the frame and display all updates
        """
        file_list = self.controller.get_api().get_files()
        for widget in self.main_frame.winfo_children():
            widget.after(0, widget.destroy)
        self.buttons = []
        columns = 6
        cell_size = 120

        for col in range(columns):
            self.main_frame.grid_columnconfigure(col, weight=1, uniform="file_grid")

        for i, file_data in enumerate(file_list):
            row = i // columns  
            col = i % columns   

            file_frame = FileButton(self.main_frame, width=cell_size, height=cell_size, file_data=file_data, controller=self.controller)
            file_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            self.buttons.append(file_frame)

class FileButton(ctk.CTkFrame):
    """
    This class represents a "file button".
    A file button is the frame surronding the file icon and name, so every mouse click in that area is considered as an action related to that specific file 
    """
    def __init__(self, master, width, height, file_data, controller):

        ctk.CTkFrame.__init__(self, master, width=width, height=height)

        self.controller = controller
        self.master = master
        self.file_data = file_data

        self.file_icon = ctk.CTkImage(light_image=Image.open("resources/file_icon.png"), size=(40, 40))

        icon_label = ctk.CTkLabel(self, image=self.file_icon, text="")
        icon_label.pack(pady=(5, 0))

        name_label = ctk.CTkLabel(self, text=self.file_data["name"], font=("Arial", 9), wraplength=90, justify="center")
        name_label.pack(pady=(0, 5))

        # Connect all file related content to do the same action when clicked (open the context_menu)
        self.bind("<Button-1>", lambda e, file_id=self.file_data["id"]: self.on_file_click(file_id, e))
        icon_label.bind("<Button-1>", lambda e, file_id=self.file_data["id"]: self.on_file_click(file_id, e))
        name_label.bind("<Button-1>", lambda e, file_id=self.file_data["id"]: self.on_file_click(file_id, e))

        # Create a context menu using CTkFrame
        self.context_menu = OptionMenu(master, self.controller, [
            {
                "label": "Download File",
                "color": "blue",
                "event": lambda: Thread(target=self.download_file_from_cloud, args=(self.file_data["id"],), daemon=True).start()
             },
             {
                 "label": "Delete File",
                 "color": "red",
                 "event": lambda: Thread(target=self.delete_file_from_cloud, args=(self.file_data["id"],), daemon=True).start()
             }
        ])

        # When clicking anywhere on the screen, close the context_menu
        master.bind("<Button-1>", lambda event: self.context_menu.hide_context_menu(), add="+")

    def download_file_from_cloud(self, file_id):
        self.controller.get_api().download_file(file_id)
        self.master.master.refresh()

    def delete_file_from_cloud(self, file_id):
        self.controller.get_api().delete_file(file_id)
        self.master.master.refresh()

    def on_file_click(self, file_id, event=None):
        """
        When clicking on a file, open the context menu for that file, double clicking means open-close the context menu.
        Click on a file close any other open context menu.
        """
        print(f"File clicked: {file_id}")
        self.controller.button_clicked(self, [self.context_menu])
        if self.context_menu.context_hidden:
            self.context_menu.lift()
            self.context_menu.show_context_menu(event.x_root - self.master.winfo_rootx(), event.y_root - self.master.winfo_rooty())
        else:
           self.context_menu.hide_context_menu()
              
class OptionMenu(ctk.CTkFrame):
    """
    Class to create the context menue option bar
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

class SharePage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

    def refresh(self):
        """
        Share page refresh - as of now we donr need this functionality
        """
        pass