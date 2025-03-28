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
        
        # Initializing frames to an empty dictionary
        self.frames = {} 

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
        if self.api.manager:
            self.api.manager.sync_to_clouds()
        if messagebox.askokcancel("Quit", "Are you sure you want to exit?"):
            if self.api.manager:
                self.api.manager.delete_fd()
                self.api.manager.stop_sync_thread()
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

    def change_folder(self, path):
        self.frames[MainPage].change_folder(path)
        

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
        This function is called when a user hits the submit button after typing the email address.
        The function handles the login process. If successful, it passes control to the MainPage class to display the main page.
        """
        self.submit_button.configure(state="disabled")
        # Add the retry button
        if hasattr(self, 'error_label'):
            self.error_label.grid_forget()
        
        # Load GIF
        self.gif = Image.open("resources/loading-gif.gif")
        self.frames = [ctk.CTkImage(self.gif.copy().convert("RGBA").resize((100, 100)))]

        # Extract all frames
        try:
            while True:
                self.gif.seek(self.gif.tell() + 1)
                self.frames.append(ctk.CTkImage(self.gif.copy().convert("RGBA").resize((100, 100)))
            )
        except EOFError:
            pass

        # Create a label for the GIF and place it under the submit button
        self.gif_label = ctk.CTkLabel(self, image=None, text="")
        self.gif_label.grid(row=4, column=0, pady=(10, 0), sticky="n")

        # Start animation
        self.frame_iterator = itertools.cycle(self.frames)
        self.update_gif()

        email = self.entry.get()
        result = self.controller.get_api().authenticate(email)
        
        if not result:
            self.__show_error("Error While connecting to the Cloud", self.controller.show_frame(LoginPage))
        else:
            self.controller.show_frame(MainPage)
    
    def update_gif(self):
        """Loop through frames"""
        self.gif_label.configure(image=next(self.frame_iterator))
        self.after(100, self.update_gif)  # Adjust speed as needed (100ms)

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

        # Display the error message
        self.error_label = ctk.CTkLabel(self, text=error_message, font=("Arial", 12), text_color="red")
        self.error_label.grid(row=4, column=0, pady=20, sticky="n")

        self.retry_button = ctk.CTkButton(self, text="Retry", command=self.__handle_login, width=200, fg_color="#3A7EBF")
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
        
        root_folder = Folder(self, controller, "/")
        self.folders = {"/": root_folder}
        self.main_frame = root_folder
        self.main_frame.pack(fill = ctk.BOTH, expand = True)

        self.curr_path = "/EncryptoSphere"

        # Create a label that will display current location
        self.url_label = ctk.CTkLabel(self, text=self.curr_path, anchor="e", fg_color="gray30", corner_radius=10)
        self.url_label.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")

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
        self.controller.get_api().upload_file(os.path.normpath(file_path), self.main_frame.path)
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
        self.controller.get_api().upload_folder(os.path.normpath(folder_path), self.main_frame.path)
        self.refresh()

    def change_folder(self, path):
        """
        Changes the folder viewed in main_frame
        """

        self.main_frame.pack_forget()
        if path in self.folders:
            self.main_frame = self.folders[path]
            
        else:
            new_folder = Folder(self, self.controller, path)
            self.folders[path] = new_folder
            self.main_frame = new_folder

        self.main_frame.refresh()
        self.main_frame.lift()
            
    def refresh(self):
        """
        Refresh the frame and display all updates
        """
        self.main_frame.refresh()
    
    

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


    def refresh(self):
        """
        Refresh the frame and display all updates
        """
        file_list, folder_list = self.controller.get_api().get_files(self.path)
        for widget in self.winfo_children():
            widget.after(0, widget.destroy)
        columns = 6
        cell_size = 120

        for col in range(columns):
            self.grid_columnconfigure(col, weight=1, uniform="file_grid")
        index = 0
        for folder in folder_list:
            row = index // columns  
            col = index % columns   

            file_frame = FolderButton(self, width=cell_size, height=cell_size, folder_path=folder, controller=self.controller)
            file_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            index += 1

        for file in file_list:
            row = index // columns  
            col = index % columns   

            file_frame = FileButton(self, width=cell_size, height=cell_size, file_data=file, controller=self.controller)
            file_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            index += 1

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
        self.bind("<Button-1>", lambda e: self.on_button1_click(e))
        icon_label.bind("<Button-1>", lambda e: self.on_button1_click(e))
        name_label.bind("<Button-1>", lambda e: self.on_button1_click(e))
        self.bind("<Button-2>", lambda e: self.on_button2_click(e))
        icon_label.bind("<Button-2>", lambda e: self.on_button2_click(e))
        name_label.bind("<Button-2>", lambda e: self.on_button2_click(e))
        self.bind("<Double-Button-1>", lambda e: self.on_double_click(e))
        icon_label.bind("<Double-Button-1>", lambda e: self.on_double_click(e))
        name_label.bind("<Double-Button-1>", lambda e: self.on_double_click(e))
    
    def on_button1_click(self, event=None):
        pass

    def on_double_click(self, event=None):
        pass
    
    def on_button2_click(self, event=None):
        pass

class FileButton(IconButton):
    """
    This class represents a "file button".
    A file button is the frame surronding the file icon and name, so every mouse click in that area is considered as an action related to that specific file 
    """
    def __init__(self, master, width, height, file_data, controller):
        IconButton.__init__(self, master, width, height, "resources/file_icon.png", file_data["name"], controller)
        self.file_data = file_data

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
        self.controller.register_context_menu(self.context_menu)

    def download_file_from_cloud(self, file_id):
        self.controller.get_api().download_file(file_id)
        self.master.master.refresh()

    def delete_file_from_cloud(self, file_id):
        self.controller.get_api().delete_file(file_id)
        self.master.master.refresh()

    def on_button1_click(self, event=None):
        """
        When clicking on a file, open the context menu for that file, double clicking means open-close the context menu.
        Click on a file close any other open context menu.
        """
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

class FolderButton(IconButton):
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

        # Create a context menu using CTkFrame
        self.context_menu = OptionMenu(master, self.controller, [
            {
                "label": "Download File",
                "color": "blue",
                "event": lambda: self.controller.get_api().download_folder(self.folder_path)
             },
             {
                 "label": "Delete File",
                 "color": "red",
                 "event": lambda: self.controller.get_api().delete_folder(self.folder_path) # maybe add "ARE YOU SURE?"
             }
        ])
        self.controller.register_context_menu(self.context_menu)

    def on_double_click(self, event=None):
        self.controller.change_folder(self.folder_path)
    
    def on_button2_click(self, event=None):
        if self.context_menu.context_hidden:
            self.context_menu.lift()
            self.context_menu.show_context_menu(event.x_root - self.master.winfo_rootx(), event.y_root - self.master.winfo_rooty())
        else:
            self.context_menu.hide_context_menu()

class SharePage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        
        self.controller = controller

        ctk.CTkFrame.__init__(self, parent)

        
        self.side_bar = ctk.CTkFrame(self, fg_color="gray25", corner_radius=0)
        self.side_bar.pack(side = ctk.LEFT,fill="y", expand = False)

        encryptosphere_label = ctk.CTkLabel(self.side_bar, text="EncryptoSphere", font=("Verdana", 15))
        encryptosphere_label.pack(anchor="nw", padx=10, pady=10, expand = False)

        self.back_button = ctk.CTkButton(self.side_bar, text="Back ⏎",
                                                 command=lambda: self.back_to_main_window(),
                                                 width=120, height=30, fg_color="gray25", hover=False)
        self.back_button.pack(anchor="nw", padx=10, pady=5, expand=False)

        self.back_button.bind("<Enter>", lambda e: self.set_bold(self.back_button))
        self.back_button.bind("<Leave>", lambda e: self.set_normal(self.back_button))

        self.share_folder_button = ctk.CTkButton(self.side_bar, text="New Share",
                                      command=lambda: self.open_sharing_window(),
                                      width=120, height=30, fg_color="gray25", hover=False)
        self.share_folder_button.pack(anchor="nw", padx=10, pady=10, expand = False)

        self.share_folder_button.bind("<Enter>", lambda e: self.set_bold(self.share_folder_button))
        self.share_folder_button.bind("<Leave>", lambda e: self.set_normal(self.share_folder_button))

        
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.pack(fill = ctk.BOTH, expand = True)


    def set_bold(self, button):
        """ Change the button text to bold on hover. """
        button.configure(font=("Verdana", 13, "bold"))

    def set_normal(self, button):
        """ Revert the button text to normal when not hovered. """
        button.configure(font=("Verdana", 13))
    
    def back_to_main_window(self):
        self.controller.get_api().change_session()
        self.controller.show_frame(MainPage)

    def open_sharing_window(self):
        """
        This function opens the upload menu with inputs for folder name and email list.
        """ 
        new_window = ctk.CTkToplevel(self)
        new_window.title("New Share")
        new_window.lift()  # Bring to front
        new_window.transient(self)  # Keep it on top of the main window

        # Get the position and size of the parent (controller) window
        main_x = self.controller.winfo_x()
        main_y = self.controller.winfo_y()
        main_w = self.controller.winfo_width()
        main_h = self.controller.winfo_height()
        new_w, new_h = 400, 350  # Size of the new window

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

        email_inputs = []  # List to hold email input fields

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
            Thread(target=self.controller.get_api().create_shared_session, args=(folder_name, emails,), daemon=True).start()

            # Close the new window
            new_window.destroy()

        # Create new share button (this now does both actions: create share and close the window)
        create_share_button = ctk.CTkButton(scrollable_frame, text="Create New Share", command=create_new_share)
        create_share_button.grid(row=100, column=0, pady=50, padx=100, sticky="s")

        # Adjust the scrollbar to make it thinner (no slider_length argument)
        new_window.after(100, lambda: scrollable_frame._scrollbar.configure(width=8))  # Adjust the width of the scrollbar


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
        file_list = self.controller.get_api().get_shared_folders()
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

            file_frame = SharedFolderButton(self.main_frame, width=cell_size, height=cell_size, file_data=file_data, controller=self.controller)
            file_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            self.buttons.append(file_frame)


class SharedFolderButton(IconButton):
    def __init__(self, master, width, height, file_data, controller):

        super().__init__(self, master, width, height, "resources/folder_icon.png", file_data["name"], controller)
        self.controller = controller
        self.master = master
        self.file_data = file_data

        # Create a context menu using CTkFrame
        self.context_menu = OptionMenu(master, self.controller, [
            {
                "label": "Add Member",
                "color": "green4",
                "event": lambda: Thread(target=self.download_file_from_cloud, args=(self.file_data["id"],), daemon=True).start()
             },
             {
                 "label": "Remove member",
                 "color": "green4",
                 "event": lambda: Thread(target=self.delete_file_from_cloud, args=(self.file_data["id"],), daemon=True).start()
             },
                         {
                "label": "Leave Share",
                "color": "red",
                "event": lambda: Thread(target=self.download_file_from_cloud, args=(self.file_data["id"],), daemon=True).start()
             },
             {
                 "label": "Delete Share",
                 "color": "red",
                 "event": lambda: Thread(target=self.delete_file_from_cloud, args=(self.file_data["id"],), daemon=True).start()
             }
        ])

        self.controller.register_context_menu(self.context_menu)

    def download_file_from_cloud(self, file_id):
        self.controller.get_api().download_file(file_id)
        self.master.master.refresh()

    def delete_file_from_cloud(self, file_id):
        self.controller.get_api().delete_file(file_id)
        self.master.master.refresh()

    def on_button1_click(self, event=None):
        """
        When clicking on a file, open the context menu for that file, double clicking means open-close the context menu.
        Click on a file close any other open context menu.
        """
        self.controller.button_clicked(self, [self.context_menu])
        if self.context_menu.context_hidden:
            self.context_menu.lift()
            self.context_menu.show_context_menu(event.x_root - self.master.winfo_rootx(), event.y_root - self.master.winfo_rooty())
        else:
           self.context_menu.hide_context_menu()