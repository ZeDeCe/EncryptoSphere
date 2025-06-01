"""
This is the app UI 
"""
import customtkinter as ctk
from PIL import Image
from customtkinter import filedialog
import os
from threading import Thread
import tkinter.messagebox as messagebox
import re



def clickable(cls):
    original_init = cls.__init__ if hasattr(cls, '__init__') else lambda f: None
    #original_del = cls.__del__ if hasattr(cls, '__del__') else lambda f: None
    
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.controller = App.controller

        self.bound = self.bind("<Button>", self.clicked, "+") # shaqed

        if isinstance(self, ctk.CTkScrollableFrame) and hasattr(self, "_parent_canvas"):
            self.bound = self._parent_canvas.bind("<Button>", self.clicked, "+")

    def clicked(self, event):
        self.controller.button_clicked(self)
        event.widget.focus_set()

    cls.__init__ = new_init
    cls.clicked = clicked

    if cls.__name__ == "CTkButton":
        old_clicked = cls._clicked if hasattr(cls, "_clicked") else lambda self, event: None
        def button_clicked(self, event):
            self.clicked(event)
            return old_clicked(self, event)
        cls._clicked = button_clicked
    return cls

clickable(ctk.CTkFrame)
clickable(ctk.CTkLabel)
clickable(ctk.CTkScrollableFrame)
clickable(ctk.CTkButton)
clickable(ctk.CTkInputDialog)
clickable(ctk.CTkProgressBar)

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
    
    controller = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, 'instance'):
            cls.instance = super(App, cls).__new__(cls)
        return cls.instance
    def get_global_app() -> ctk.CTk:
        """
        Get the global app instance
        """
        return App.instance
    
    def __init__(self, gateway):
        app = self
        App.controller = self
        ctk.CTk.__init__(self)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("resources/rime.json")
        self.title("EncryptoSphere")
        self.iconbitmap("resources/EncryptoSphere_logo.ico")
 
        # As of now we are using specific sizing, on the advanced ui we will need to make dynamic sizing
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry("900x600+%d+%d" % (screen_width/2-325, screen_height/2-200))
        
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
        self.current_popup : Popup = None
        
        # Creating the frames
        for F in (EmailPage, LoginCloudsPage, LocalPasswordPage, RegistrationPage, MainPage):
            frame = F(container, self)
            self.frames[F] = frame  
            frame.grid(row=0, column=0, sticky="nsew")
        
        # Show the start page (as of this POC, login to the clouds)
        self.show_frame(EmailPage)
        

    def show_frame(self, cont):
        """
        Display the given frame
        @param cont: The frame to be displayed
        """
        frame = self.frames[cont]
        self.current_frame = frame
        frame.refresh()
        frame.tkraise()
    
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
            self.api.manager.cleanup_temp_folder() 
            self.api.stop_sync_new_sessions_task()
    
    def set_popup(self, popup):
        if self.current_popup is not None:
            self.current_popup.hide_popup()
        self.current_popup = popup

    def remove_popup(self, popup):
        if self.current_popup == popup:
            self.current_popup = None
    
    def button_clicked(self, button):
        """
        When any button is clicked, we need to close all opend context_menu(s)
        @param button: The button that was clicked
        @param ignore_list: List of context menus that should not be closed 
        """
        if self.current_popup is None:
            return
        parent = button
        while parent != self and parent != self.container:
            if parent == self.current_popup:
                return
            try:
                parent = parent.master
            except:
                print("Got to end of parents but did not hit break, flawed code")
                break
        
        self.current_popup.hide_popup()

    def change_folder(self, path):
        """
        Change the folder in the main page to the given path
        @param path: The path to the folder to be changed to
        """
        self.frames[MainPage].change_folder(path)
    
    def change_session(self, uid):
        """
        Change the session in the main page to the given path
        @param path: The path to the session to be changed to
        """
        self.api.change_session(uid)
        self.frames[MainPage].change_session(uid if uid is not None else "0")

    def add_message_label(self, message):
        """
        Add a message label to the main page
        @param message: The message to be displayed
        """
        return self.frames[MainPage].add_message_label(message)
    
    def remove_message(self, label):
        """
        Remove a message label from the main page
        @param label: The label to be removed
        """
        self.frames[MainPage].remove_message(label)
    
    def show_message_notification(self, desc_text, title, on_confirm):
        """
        Show a message notification to the user
        @param desc_text: The text to be displayed in the notification
        @param title: The title of the notification
        @param on_confirm: The function to be called when the user confirms the notification
        """
        self.frames[MainPage].show_message_notification(desc_text, title, on_confirm)

    def refresh(self):
        """
        Refresh the current frame
        """
        self.frames[MainPage].refresh()

    def get_main_page(self):
        """
        Get the main page frame
        """
        return self.frames[MainPage]

@clickable
class LoadingPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        ctk.CTkFrame.__init__(self, parent)
        self.controller = controller
        
        # loading bar
        self.p = ctk.CTkProgressBar(self, orientation="horizontal", mode="indeterminate", width=300)
        self.p.pack(anchor=ctk.CENTER, expand=True, fill=ctk.BOTH)

    
    def stop(self):
        """
        Stop the loading bar
        """
        self.p.stop()
    def start(self):
        """
        Start the loading bar
        """
        self.p.start()
        
@clickable
class FormPage(ctk.CTkFrame):
    """
    This class creates the Form page frame -  Where user enters email and authenticates to the different clouds.
    This class inherits ctk.CTkFrame class.
    """
    def __init__(self, parent, controller, title, message, input_placeholder_text, button_text, func, error_func ,error_message):
        ctk.CTkFrame.__init__(self, parent)
        self.controller = controller
        self.func = func
        self.error_message = error_message
        self.error_func = error_func

        # === Left Image Panel ===
        self.left_panel = ctk.CTkFrame(self, width=320, fg_color="#5389C7", corner_radius=0)
        self.left_panel.place(relx=0, rely=0, relwidth=0.4, relheight=1)

        self.image = ctk.CTkImage(Image.open("resources/main_logo.png"), size=(320, 320))
        self.image_label = ctk.CTkLabel(self.left_panel, image=self.image, text="")
        self.image_label.place(relx=0.5, rely=0.5, anchor="center")
        


        # === Right Form Panel ===
        self.right_panel = ctk.CTkFrame(self, fg_color="#2B2D2F", corner_radius=0)
        self.right_panel.place(relx=0.4, rely=0, relwidth=0.6, relheight=1)

        # Title Label
        label = ctk.CTkLabel(self.right_panel, text=title, 
                             font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"), anchor="w")
        label.pack(pady=(40, 8), padx=20)

        # Email Label
        self.message = ctk.CTkLabel(self.right_panel, text=message, width=300, font=ctk.CTkFont(family="Segoe UI", size=20), anchor="w")
        self.message.pack(pady=(60, 10), padx=20)

        # Email Entry Field
        self.entry = ctk.CTkEntry(self.right_panel, placeholder_text=input_placeholder_text, width=300, height=35)
        self.entry.pack(padx=20)

        # Submit Button
        self.submit_button = ctk.CTkButton(self.right_panel, text=button_text, command=self.submit, width=300, height=35, corner_radius=10)
        self.submit_button.pack(pady=(20, 60), padx=20)

        self.loadingpage = LoadingPage(self.right_panel, controller)
    
    def show_loading(self):
        self.loadingpage.pack(anchor=ctk.CENTER)
        
        self.loadingpage.start()
        self.loadingpage.lift()
        self.update_idletasks()

    def remove_loading(self):
        self.loadingpage.stop()
        self.loadingpage.pack_forget()
        

    def refresh(self):
        """
        Login page refresh - as of now we dont need this functionality
        """
        pass
    
    def submit(self):
        """
        This function is called when a user hits the submit button after typing the email address.
        The function handles the login process. If successful, it passes control to the MainPage class to display the main page.
        """
        self.submit_button.configure(state="disabled")

        user_input = self.entry.get()
        self.show_loading()
        if not self.func(user_input):
            if self.error_func is not None:
                self.error_func()



@clickable
class EmailPage(FormPage):
    """
    This class creates the Login page frame -  Where user enters email and authenticates to the different clouds.
    This class inherits ctk.CTkFrame class.
    """
    def __init__(self, parent, controller):
        FormPage.__init__(self, parent, controller, "Welcome to EncryptoSphere", "Email address ", "Your Email Address", "Login", self.handle_login, self.error_func, "Error while connecting to the Clouds")
        self.error_label = ctk.CTkLabel(self.right_panel, text="", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="red")
        self.error_label.pack()
    
    def error_func(self):
        """
        This function is called when the login process fails.
        It displays an error message and enables the submit button.
        """
        self.remove_loading()
        self.error_label.configure(text=self.error_message)
        self.submit_button.configure(state="normal")

    def handle_login(self, email):
        """
        This function is called when a user hits the submit button after typing the email address.
        The function handles the login process. If successful, it passes control to the MainPage class to display the main page.
        """
        if re.match(r"[^@]+@[^@]+\.[^@]+", email) is None:
            self.error_message = "Invalid email address format"
            return False
        
        self.controller.get_api().set_email(email)
        return self.controller.get_api().clouds_authenticate_by_token(lambda f: self.controller.show_frame(LoginCloudsPage))

@clickable
class LocalPasswordPage(FormPage):
    """
    This class creates the Login page frame -  Where user enters email and authenticates to the different clouds.
    This class inherits ctk.CTkFrame class.
    """
    def __init__(self, parent, controller):
        FormPage.__init__(self, parent, controller, "", "Password ", "Your Password", "Login", self.validate_password, self.error_login,"Wrong password, Please try again")
        self.error_label = ctk.CTkLabel(self.right_panel, text="", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="red")
        self.error_label.pack()
        
    def validate_password(self, password):
        """
        This function is called when a user hits the submit button after typing the email address.
        The function handles the login process. If successful, it passes control to the MainPage class to display the main page.
        """
        return self.controller.get_api().app_authenticate(lambda f: self.controller.show_frame(MainPage) if f.result() == True else self.error_login(f.result()), password)


    def error_login(self, message=None):
        if message is None:
            message = self.error_message
        self.remove_loading()
        self.__show_error(self.error_message, lambda: False)
    
    def __show_error(self, error_message, func):
        """
        If authentication to the clouds fails, display the error and add retry button.
        Remove the submit button and the GIF.
        """
        # Display the error message
        self.error_label.configure(text=error_message)
        self.submit_button.configure(state="normal")

@clickable
class LoginCloudsPage(ctk.CTkFrame):
    """
    This class creates the Login page frame -  Where user enters email and authenticates to the different clouds.
    This class inherits ctk.CTkFrame class.
    """
    def __init__(self, parent, controller):
        ctk.CTkFrame.__init__(self, parent)
        
        self.controller = controller
        self.cloud_list = self.controller.get_api().get_clouds()
        
        # === Left Image Panel ===
        self.left_panel = ctk.CTkFrame(self, width=320, fg_color="#5389C7", corner_radius=0)
        self.left_panel.place(relx=0, rely=0, relwidth=0.4, relheight=1)

        self.image = ctk.CTkImage(Image.open("resources/main_logo.png"), size=(320, 320))
        self.image_label = ctk.CTkLabel(self.left_panel, image=self.image, text="")
        self.image_label.place(relx=0.5, rely=0.5, anchor="center")
        


        # === Right Form Panel ===
        self.right_panel = ctk.CTkFrame(self, width=580,fg_color="#2B2D2F", corner_radius=0)
        self.right_panel.place(relx=0.4, rely=0, relwidth=0.6, relheight=1)

        self.right_panel.grid_columnconfigure(0, weight=1)
        self.right_panel.grid_rowconfigure((0, 1, 2, 3, 4, 5), weight=1)

        # Title Label
        self.message = ctk.CTkLabel(self.right_panel, text="Choose Your Clouds", font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"))
        self.message.grid(row=0, column=0, pady=(40, 35), padx=20, columnspan=5, sticky="n")

        # Clouds container
        self.clouds_container = ctk.CTkFrame(self.right_panel, corner_radius=0)
        self.clouds_container.grid(row=1, column=0, columnspan=3, padx=50, sticky="nsew")
                
        # Submit Button
        self.submit_button = ctk.CTkButton(self.right_panel, text="Create New Account", command=self.__handle_login, width=300, height=35, corner_radius=10)
        self.submit_button.grid(row=3, column=0, padx=20, pady=(0, 60), sticky="n")
        self.submit_button.configure(state="disabled")
        self.loadingpage = LoadingPage(self, controller)

        self.notice_message()
    
    def show_loading(self):
        self.loadingpage.grid(row=4, column=0, sticky="n")
        
        self.loadingpage.start()
        self.loadingpage.lift()
        self.update_idletasks()

    def remove_loading(self):
        self.loadingpage.stop()
        self.loadingpage.grid_forget()

    def notice_message(self):
        # Remove existing notice label if present
        if hasattr(self, 'notice_label'):
            self.notice_label.grid_forget()
            self.notice_label.destroy()
            del self.notice_label

        # Add notice label if the button text is "Create New Account"
        if self.submit_button.cget("text").lower() == "create new account":
            authenticated_clouds = self.controller.get_api().get_authenticated_clouds()
            cloud_names = ", ".join([cloud.get_name_static() if hasattr(cloud, "get_name_static") else str(cloud) for cloud in authenticated_clouds])
            notice_text = (
                "Notice: Your account will be created using the clouds you select here. This cannot be changed later!\n "
                "If you already have an account, please login to at least one cloud and you'll be moved to the authentication page."
            )
            self.notice_label = ctk.CTkLabel(self.right_panel, text=notice_text, font=ctk.CTkFont(family="Segoe UI", size=12), wraplength=400, justify="center")
            self.notice_label.grid(row=5, column=0, padx=20, pady=(0, 10), sticky="n")

    def refresh(self):
        """
        Login page refresh - as of now we dont need this functionality
        """
        self.authenticated_clouds = self.controller.get_api().get_authenticated_clouds()
        for i, cloud in enumerate(self.cloud_list):
            icon_path = cloud.get_icon_static()
            is_auth = False
            for cloud_object in self.authenticated_clouds:
                if isinstance(cloud_object, cloud):
                    icon_path = cloud_object.get_icon()
                    is_auth = True
                    break
            cloud_button = ctk.CTkButton(self.clouds_container, image=ctk.CTkImage(Image.open(icon_path), size=(100, 100)), text="", hover=True, fg_color="#2B2D2F", corner_radius=20, width=90, height=90)
            cloud_button.pack(side=ctk.LEFT, expand=True)
            cloud_button.pack_propagate(False)
            if not is_auth:
                cloud_button.configure(command=lambda cloud=cloud, cloud_button=cloud_button: self.cloud_button_clicked(cloud, cloud_button))
            else:
                self.submit_button.configure(state="normal", width=200)
                cloud_button.configure(state="disabled")  # Disable the button after successful authentication
        if self.controller.get_api().get_metadata_exists():
            self.submit_button.configure(text="Continue to Login")
        self.notice_message()
    
    
    def cloud_button_clicked(self, cloud, cloud_button):
        self.controller.get_api().cloud_authenticate(lambda f, cloud=cloud, cloud_button=cloud_button : self.cloud_button_run(f, cloud_button), cloud.get_name_static())
                                                     
    
    def cloud_button_run(self, f, cloud_button):
        
        if f.result():
            cloud_button.configure(image=ctk.CTkImage(Image.open(f.result().get_icon()), size=(100, 100)))
            cloud_button.configure(state="disabled")  # Disable the button after successful authentication
            self.submit_button.configure(state="normal")
            self.notice_message()
        else:
            self.__error_login()
        if self.controller.get_api().get_metadata_exists():
            self.submit_button.configure(text="Continue to Login")

    def __handle_login(self):
        """
        This function is called when a user hits the submit button after typing the email address.
        The function handles the login process. If successful, it passes control to the MainPage class to display the main page.
        """
        self.submit_button.configure(state="disabled")
        
        # Remove error label and block the button
        if hasattr(self, 'error_label'):
            self.error_label.grid_forget()
        if hasattr(self, 'retry_button'):
            self.retry_button.configure(state="disabled")
        if self.controller.get_api().get_authenticated_clouds():
            if self.controller.get_api().get_metadata_exists():
                self.controller.show_frame(LocalPasswordPage)
            else:
                self.controller.show_frame(RegistrationPage)
        else:
            self.__error_login()


    def __error_login(self):
        self.remove_loading()
        self.__show_error("You must login to at least one cloud to continue", self.controller.show_frame(LoginCloudsPage))
    
    def __show_error(self, error_message, func):
        """
        If authentication to the clouds fails, display the error and add retry button.
        Remove the submit button and the GIF.
        """
        pass
        # # Display the error message
        # self.error_label = ctk.CTkLabel(self, text=error_message, font=("Arial", 12), text_color="red")
        # self.error_label.grid(row=4, column=0, pady=3, sticky="n")



@clickable
class RegistrationPage(ctk.CTkFrame):
    """
    This class creates the Registration page frame.
    """
    def __init__(self, parent, controller):
        ctk.CTkFrame.__init__(self, parent)
        self.controller = controller

        # Title Label
        label = ctk.CTkLabel(self, text="Create Your Account", 
                             font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"))
        label.pack(pady=(40, 20), padx=20)

        # Password Label
        self.message_pass = ctk.CTkLabel(self, text="Enter Your Password:", font=ctk.CTkFont(family="Segoe UI", size=16), anchor="w",width=300)
        self.message_pass.pack(padx=20)

        # Password Entry Field
        self.entry_pass = ctk.CTkEntry(self, placeholder_text="Your Password", width=300, height=35)
        self.entry_pass.pack(padx=20, pady=(0, 20))

        # Encryption Algorithm option menu
        encryption, split = self.controller.get_api().get_algorithms()
        index = -1
        for ind, cls in enumerate(encryption):
            if cls.get_name() == "AES":
                index = ind
                break
        if index != -1:
            encryption.insert(0, encryption.pop(index))
        index = -1
        for ind, cls in enumerate(split):
            if cls.get_name() == "Shamir":
                index = ind
                break
        if index != -1:
            split.insert(0, split.pop(index))

        self.message_encription = ctk.CTkLabel(self, text="Select Encryption Algorithm:", font=ctk.CTkFont(family="Segoe UI", size=16), width=300,anchor="w")
        self.message_encription.pack(padx=20)

        self.encryption_algorithm = ctk.CTkOptionMenu(self, values=[cls.get_name() for cls in encryption], command=lambda x: None, width=300, height=35)
        self.encryption_algorithm.pack(padx=20, pady=(0, 20))

        self.message_split = ctk.CTkLabel(self, text="Select Split Algorithm:", font=ctk.CTkFont(family="Segoe UI", size=16),width=300, anchor="w")
        self.message_split.pack(padx=20)

        # Split Algorithm option menu
        self.split_algorithm = ctk.CTkOptionMenu(self, values=[cls.get_name() for cls in split], command=lambda x: None, width=300, height=35)
        self.split_algorithm.pack(padx=20, pady=(0, 20))

        # Submit Button
        self.submit_button = ctk.CTkButton(self, text="Create New Account", command=self.submit, width=300, height=35, corner_radius=10)
        self.submit_button.pack(pady=(20, 0))

        self.error_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(family="Segoe UI", size=12), text_color="red")
        self.error_label.pack(pady=20)

        self.loadingpage = LoadingPage(self, controller)

    def show_loading(self):
        self.loadingpage.pack()
        self.error_label.configure(text="")
        self.loadingpage.start()
        self.loadingpage.lift()
        self.update_idletasks()

    def remove_loading(self):
        self.loadingpage.stop()
        self.loadingpage.pack_forget()

    def refresh(self):
        """
        Login page refresh - as of now we don't need this functionality
        """
        pass

    def show_error(self, error_message):
        """
        Show an error message to the user
        @param error_message: The error message to be displayed
        """
        self.remove_loading()
        self.error_label.configure(text=error_message)

    def submit(self):
        """
        This function is called when a user hits the submit button after typing the email address.
        The function handles the login process. If successful, it passes control to the MainPage class to display the main page.
        """
        self.submit_button.configure(state="disabled")

        if hasattr(self, 'retry_button'):
            self.retry_button.configure(state="disabled")

        password = self.entry_pass.get()
        if len(password) < 6:
            self.show_error("Password must be at least 6 characters long.")
            self.submit_button.configure(state="normal")
            return
        encrypt_alg = self.encryption_algorithm.get()
        split_alg = self.split_algorithm.get()
        self.show_loading()
        self.controller.get_api().create_account(lambda f: self.controller.show_frame(MainPage) if f.result() else self.show_error("Failed to create account, try again later"), password, encrypt_alg, split_alg)


    
@clickable
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
        self.side_bar = ctk.CTkFrame(self, corner_radius=0, width=200, fg_color="#3A3C41")
        self.side_bar.pack(side=ctk.LEFT, fill="y", expand=False)
        self.side_bar.pack_propagate(False)  # Prevent the side bar from resizing to fit its contents

        # Add the EncryptoSphere label to the side bar
        encryptosphere_icon = ctk.CTkImage(light_image=Image.open("resources/encryptosphere_logo.png"), size=(40, 40))
        self.encryptosphere_label = ctk.CTkLabel(self.side_bar, image=encryptosphere_icon, text="  EncryptoSphere", font=("Segoe UI", 15), compound="left")
        self.encryptosphere_label.pack(anchor="nw", padx=10, pady=10, expand=False)

        # Create the upload button and shared files button
        self.upload_button = ctk.CTkButton(self.side_bar, text=" + New ",
                                           command=lambda: self.open_upload_menu(),
                                           width=80, height=40, corner_radius=10)
        self.upload_button.pack(anchor="w", padx=10, pady=10, expand=False)
        
        home_icon = ctk.CTkImage(light_image=Image.open("resources/home_icon.png"), size=(20, 20))
        self.homepage_button = ctk.CTkButton(self.side_bar, image=home_icon, text="Home", compound="left",
                                                 command=lambda: (self.controller.change_session(None), self.search_entry.delete(0, 'end')),
                                                 width=120, height=30, hover=False, fg_color="#3A3C41", anchor="w")
        self.homepage_button.pack(anchor="w", padx=10, pady=5, expand=False)

        users_icon = ctk.CTkImage(light_image=Image.open("resources/users_icon.png"), size=(20, 20))
        self.shared_files_button = ctk.CTkButton(self.side_bar, image=users_icon, text="Shared Files",compound="left",
                                                 command=lambda: self.display_page(self.sessions_folder, options=["New Share"]),
                                                 width=120, height=30, hover=False, fg_color="#3A3C41", anchor="w")
        self.shared_files_button.pack(anchor="w", padx=10, pady=0, expand=False)

        # Bind hover events to the buttons (to change font to bold)
        self.homepage_button.bind("<Enter>", lambda e: self.set_bold(self.homepage_button), add="+")
        self.homepage_button.bind("<Leave>", lambda e: self.set_normal(self.homepage_button), add="+")

        self.shared_files_button.bind("<Enter>", lambda e: self.set_bold(self.shared_files_button))
        self.shared_files_button.bind("<Leave>", lambda e: self.set_normal(self.shared_files_button))

        self.container = ctk.CTkFrame(self, corner_radius=0)
        self.container.pack(fill = ctk.BOTH, expand = True)

        self.search_bar = ctk.CTkFrame(self.container, height=60, corner_radius=0, fg_color="#3A3C41")
        self.search_bar.pack(side=ctk.TOP, fill=ctk.X)
        self.search_bar.pack_propagate(False)  # Prevent the side bar from resizing to fit its contents

        # Add a search entry field to the search bar
        self.search_entry = ctk.CTkEntry(self.search_bar, placeholder_text="Search in EncryptoSphere", width=500, height=35, corner_radius=15)
        self.search_entry.pack(side=ctk.LEFT, padx=10, pady=10)

        # Bind the "Enter" key to trigger the search
        self.search_entry.bind("<Return>", lambda event: self.perform_search(), add="+")

        # Bind focus-out event to reset placeholder
        self.search_entry.bind("<FocusOut>", lambda event: self.reset_search_placeholder(), add="+")


        # Add refresh button to the search bar
        refresh_icon = ctk.CTkImage(light_image=Image.open("resources/refresh_icon.png"), size=(20, 20))
        self.refresh_button = ctk.CTkButton(self.search_bar, image=refresh_icon, text="",command=lambda: self.refresh_button_click(), width=20, height=20, corner_radius=20, fg_color="#2B2D2F", hover_color="gray40")
        self.refresh_button.pack(side=ctk.RIGHT, padx=10, pady=5)

        self.main_session : Session  = Session(self.container, controller, "EncryptoSphere")
        self.current_session : Session = self.main_session
        self.main_session.pack(fill=ctk.BOTH, expand=True)
        self.sessions = {"0": self.main_session}

        # Create messages pannel
        self.messages_pannel = ctk.CTkFrame(self.container, corner_radius=0)

        self.uploading_labels : list = []
        
        self.messages_pannel.lift()

        self.search_results_session = SearchResultsSession(self.container, self.controller)
        self.search_results_session.pack_forget()

        self.sessions_folder = SessionsFolder(self.container, self.controller)
        self.sessions_folder.pack_forget()

        # Initialize the context menu
        self.initialize_context_menu()

    def initialize_context_menu(self):
        """
        Initialize or recreate the context menu for the upload button.
        """
        self.context_menu = OptionMenu(self, self.controller, [
            {
                "label": "New Folder",
                "color": "#3A3C41",
                "event": lambda: self.create_new_folder()
            },
            {
                "label": "Upload File",
                "color": "#3A3C41",
                "event": lambda: self.upload_file()
            },
            {
                "label": "Upload Folder",
                "color": "#3A3C41",
                "event": lambda: self.upload_folder()
            },
            {
                "label": "New Share",
                "color": "#3A3C41",
                "event": lambda: self.open_sharing_window()
            }
        ])

    def set_bold(self, button):
        """
        Change the button text to bold on hover
        @param button: The button to be changed
        """
        button.configure(font=("Segoe UI", 13, "bold"))

    def set_normal(self, button):
        """
        Revert the button text to normal when not hovered
        @param button: The button to be changed
        """
        button.configure(font=("Segoe UI", 13))
        
    def perform_search(self):
            """
            Perform a search based on the input in the search entry field.
            """
            query = self.search_entry.get()
            print(f"Searching for: {query}")
            self.search_results_session.set_query(query)
            self.display_page(self.search_results_session)

    def reset_search_placeholder(self):
        """
        Reset the placeholder text of the search entry when it loses focus.
        """
        if not self.search_entry.get():
            self.search_entry.configure(placeholder_text="Search in EncryptoSphere")

    def open_upload_menu(self):
        """
        This function opens the upload menu using the context menu
        """
        print("Upload button clicked")
        if self.context_menu.context_hidden:
            self.context_menu.show_popup(self.upload_button.winfo_x(), self.upload_button.winfo_y()+5)
        else:
            self.context_menu.hide_popup()

    def create_new_folder(self):
        """
        If new folder option is selected in the upload_context_menu, open a dialog to let the user pick a name for the new folder
        """
        # Get the position and size of the parent window
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_width = self.winfo_width()
        parent_height = self.winfo_height()

        # Create the input dialog
        input_dialog = ctk.CTkInputDialog(text="Enter the name of the new folder:", title="Create New Folder")

        # Calculate the position to center the dialog over the parent window
        dialog_width = 300  # Approximate width of the dialog
        dialog_height = 150  # Approximate height of the dialog
        dialog_x = parent_x + (parent_width // 2) - (dialog_width // 2)
        dialog_y = parent_y + (parent_height // 2) - (dialog_height // 2)

        # Set the position of the dialog
        input_dialog.geometry(f"{dialog_width}x{dialog_height}+{dialog_x}+{dialog_y}")

        # Get the folder name from the input dialog
        folder_name = input_dialog.get_input()
        self.context_menu.hide_popup()
        if folder_name:
            folder_path = f"{self.current_session.curr_path}/{folder_name}" if self.current_session.curr_path != "/" else f"/{folder_name}"
            self.create_new_folder_in_cloud(folder_path)
    
    def create_new_folder_in_cloud(self, folder_path):
        """
        Create a new folder in the cloud and refresh the page
        @param folder_path: The path of the folder to be created
        """
        label = self.add_message_label(f"Creating folder {folder_path.split('/')[-1]}")

        self.controller.get_api().create_folder(
            lambda f: (
                self.remove_message(label),
                self.current_session.refresh(self.current_session.curr_path),
                messagebox.showerror("Application Error",str(f.exception())) if f.exception() else None
            ),
            folder_path,
        )
    
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
        folder_label = ctk.CTkLabel(scrollable_frame, text="Enter Folder Name:", anchor="w", font=ctk.CTkFont(family="Segoe UI", size=16))
        folder_label.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")
        folder_name_entry = ctk.CTkEntry(scrollable_frame, width=200)
        folder_name_entry.grid(row=1, column=0, padx=20, pady=5, sticky="w")

        # Encryption Algorithem option menu
        encryption, split =self.controller.get_api().get_algorithms()
        index = -1
        for ind,cls in enumerate(encryption):
            if cls.get_name() == self.controller.get_api().get_default_encryption_algorithm():
                index = ind
                break
        if index != -1:
            encryption.insert(0, encryption.pop(index))
        index = -1
        for ind,cls in enumerate(split):
            if cls.get_name() == self.controller.get_api().get_default_encryption_algorithm():
                index = ind
                break
        if index != -1:
            split.insert(0, split.pop(index))

        message_encription = ctk.CTkLabel(scrollable_frame, text="Select Encryption Algorithm:", font=ctk.CTkFont(family="Segoe UI", size=16))
        message_encription.grid(row=2, column=0, padx=20, sticky="w")

        encryption_algorithm = ctk.CTkOptionMenu(scrollable_frame, values=[cls.get_name() for cls in encryption], command=lambda x: None)
        encryption_algorithm.grid(row=3, column=0, padx=20, pady=(0,20), sticky="ew")

        
        message_split = ctk.CTkLabel(scrollable_frame, text="Select Split Algorithm:", font=ctk.CTkFont(family="Segoe UI", size=16))
        message_split.grid(row=4, column=0, padx=20, sticky="w")

        # Split Algorithem option menu
        split_algorithm = ctk.CTkOptionMenu(scrollable_frame, values=[cls.get_name() for cls in split], command=lambda x: None)
        split_algorithm.grid(row=5, column=0, padx=20, pady=(0,20), sticky="ew")

        # Share with header
        share_with_label = ctk.CTkLabel(scrollable_frame, text="Share with:", anchor="w", font=ctk.CTkFont(family="Segoe UI", size=16))
        share_with_label.grid(row=6, column=0, padx=20, pady=(0, 5), sticky="w")
        
        # Email list input
        email_frame = ctk.CTkFrame(scrollable_frame, fg_color=scrollable_frame.cget('fg_color'))  # Match background
        email_frame.grid(row=7, column=0, padx=20, columnspan=2, pady=0, sticky="w")

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
        plus_button = ctk.CTkButton(email_frame, text="+", command=add_email_input, width=30, height=30, corner_radius=15, font=ctk.CTkFont(family="Segoe UI", size=16))
        plus_button.grid(row=1, column=1, padx=10, pady=5)

        # Function to handle the creation of new share
        def create_new_share():
            folder_name = folder_name_entry.get()
            emails = [email.get() for email in email_inputs]
            print(f"Creating share with folder: {folder_name} and emails: {emails}")
            label = self.add_message_label(f"The folder {folder_name} is being shared")
            # Call a new function with the folder and emails (replace this with your logic)
            self.controller.get_api().create_shared_session(lambda f: (self.refresh(), self.remove_message(label)), folder_name, emails, encryption_algorithm.get(), split_algorithm.get())
            # Close the new window
            new_window.destroy()

        # Create new share button (this now does both actions: create share and close the window)
        create_share_button = ctk.CTkButton(scrollable_frame, text="Create New Share", command=create_new_share)
        create_share_button.grid(row=100, column=0, pady=50, padx=100, sticky="s")

        # Adjust the scrollbar to make it thinner (no slider_length argument)
        new_window.after(100, lambda: scrollable_frame._scrollbar.configure(width=8))  # Adjust the width of the scrollbar
    

    def upload_file(self):
        """
        If upload file option is selected in the upload_context_menu, open file explorer and let the user pick a file
        """
        file_path = filedialog.askopenfilename()
        self.context_menu.hide_popup()
        print(file_path)
        if file_path:
            self.upload_file_to_cloud(file_path)

    def upload_file_to_cloud(self, file_path):
        """
        Upload file to the cloud and refresh the page
        @param file_path: The path of the file to be uploaded
        """
        label = self.add_message_label(f"Uploading file {file_path.split('/')[-1]}")

        self.controller.get_api().upload_file(
            lambda f: (
                self.remove_message(label),
                self.current_session.refresh(self.current_session.curr_path),
                messagebox.showerror("Application Error",str(f.exception())) if f.exception() else None
            ),
            os.path.normpath(file_path),
            self.current_session.curr_path
        )
    
    def upload_folder(self):
        """
        If upload folder option is selected in the upload_context_menu, open file explorer and let the user pick a folder
        """
        folder_path = filedialog.askdirectory()
        self.context_menu.hide_popup()
        if folder_path:
            self.upload_folder_to_cloud(folder_path) # This function returns immediately

    def upload_folder_to_cloud(self, folder_path):
        """
        Upload folder to the cloud and refresh the page
        @param folder_path: The path of the folder to be uploaded
        """
        label = self.add_message_label(f"Uploading folder {folder_path.split('/')[-1]}")

        self.controller.get_api().upload_folder(
            lambda f: (
                self.remove_message(label),
                self.current_session.refresh(self.current_session.curr_path),
                messagebox.showerror("Application Error",str(f.exception())) if f.exception() else None
            ),
            os.path.normpath(folder_path),
            self.current_session.curr_path
        )

    def add_message_label(self, message):
        # Create a new label for the uploading file
        self.messages_pannel.place(rely=1.0, anchor="sw")
        self.messages_pannel.lift()
        
        uploading_label = ctk.CTkLabel(self.messages_pannel, text=message, anchor="w", corner_radius=0, padx=10, pady=5)
        uploading_label.pack(side="bottom", pady=2, padx=10, anchor="w")
        uploading_label.lift()  # Ensure the label is on top of all frames

        self.uploading_labels.append(uploading_label)
        return uploading_label
    
    def remove_message(self, label):
        """
        Remove the uploading message for the completed file and reorder the labels
        @param file_path: The path of the file that finished uploading
        """

        if hasattr(self, 'uploading_labels') and label and label in self.uploading_labels:
            # Forget the label for the completed file
            label.pack_forget()
            self.uploading_labels.remove(label)
        else:
            print("Label not found in uploading_labels")
            return
        if not self.uploading_labels:
            self.messages_pannel.place_forget()

    def show_message_notification(self, desc_text, title, on_confirm):
    # Ensure the MessageNotification window is not constrained by the FolderButton size
        self.notification_window = MessageNotification(
            controller=self.controller,
            master = self,  # Use the main window as the parent
            title = title,  
            description=desc_text,
            on_confirm=on_confirm
        )
        self.notification_window.lift()

    def change_folder(self, path):
        """
        Call this function to let the mainpage know that a folder change in the current session has occurred
        """
        self.current_session.change_folder(path)
        self.messages_pannel.lift()
        if hasattr(self, 'uploading_labels'):
            for label in self.uploading_labels:
                label.lift()  # Ensure the label is on top of all frames

    def display_page(self, page, options=None):
        if options is not None:
            self.context_menu.change_options(options)
        else:
            self.context_menu.show_all_options()
        if self.current_session is not None:
            self.current_session.pack_forget()
        self.current_session = page
        page.pack(fill=ctk.BOTH, expand=True)
        page.lift()
        page.refresh()

    def change_session(self, uid):
        session = None
        if isinstance(uid, str):
            session = self.sessions.get(uid)
            if session is None:
                self.sessions[uid] = Session(self.container, self.controller, uid.split("$")[0])
                session = self.sessions[uid]
        elif isinstance(uid, Session):
            session = uid
        else:
            raise Exception("Is not a valid session")
        if self.current_session is not None:
            self.current_session.pack_forget()
        self.context_menu.show_all_options()
        self.current_session = session
        self.current_session.pack(fill=ctk.BOTH, expand=True)
        self.current_session.change_folder("/")
        self.current_session.refresh()
        self.current_session.lift()
        self.messages_pannel.lift()

    def refresh(self):
        """
        Refresh the frame and display all updates
        """
        self.current_session.refresh()
    
    def refresh_button_click(self):
        """
        Refresh according to current session
        """
        if self.current_session is None:
            return
        
        self.refresh_button.configure(state="disabled")
        if self.current_session == self.sessions_folder:
            self.controller.get_api().sync_session(lambda f: (self.sessions_folder.refresh(), self.refresh_button.configure(state="normal")))
            return
        else:
            self.current_session.refresh()
            self.refresh_button.configure(state="normal")
    

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

@clickable
class Breadcrums(ctk.CTkFrame):
    def __init__(self, parent, controller : App, root : str):
        ctk.CTkFrame.__init__(self, parent, corner_radius=0)
        self.controller = controller
        folder = ctk.CTkLabel(self, text=root, anchor="w", corner_radius=0, font=ctk.CTkFont(family="Segoe UI", size=18))
        folder.pack(side="left", pady=2, padx=(5,0))
        folder.bind("<Button-1>", lambda e,p="/": self.controller.change_folder(p), add="+")
        folder.bind("<Enter>", lambda e: folder.configure(font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold")), add="+")
        folder.bind("<Leave>", lambda e: folder.configure(font=ctk.CTkFont(family="Segoe UI", size=18)), add="+")
        self.folders = [folder]

    def __create_label(self, text, path):
        folder = ctk.CTkLabel(self, text=text, anchor="w", corner_radius=0, font=ctk.CTkFont(family="Segoe UI", size=18))
        folder.pack(side="left", pady=2, padx=(5,0))
        folder.bind("<Button-1>", lambda e,p=path: self.controller.change_folder(p), add="+")
        folder.bind("<Enter>", lambda e: folder.configure(font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold")), add="+")
        folder.bind("<Leave>", lambda e: folder.configure(font=ctk.CTkFont(family="Segoe UI", size=18)), add="+")
        return folder

    def set_path(self, path : str):
        """
        Set the path of the breadcrums
        @param path: The path to be set
        """
        assert path.startswith("/"), "Path must start with '/'"
        folders = path.split("/") if path != "/" else [""]
        curr_path = ""
        i = 1 
        broken = False
        for i in range(1, len(folders)):
            f = folders[i]
            
            if len(self.folders)-1>=i and f" > {f}" == self.folders[i].cget("text"):
                curr_path += f"/{f}"
                continue
            else:
                broken = True
                break
        if not broken and path != "/":
            i += 1
        for i in range(len(self.folders)-1, i-1, -1):
            self.folders[i].pack_forget()
            self.folders[i].unbind("<Button-1>")
            self.folders[i].destroy()
            self.folders.pop(i)

        for i in range(i, len(folders)):
            curr_path += f"/{f}"
            self.folders.insert(i, self.__create_label(f" > {folders[i]}", curr_path))

        

@clickable
class Session(ctk.CTkFrame):
    """
    This class represents a session in the app, it is a subclass of CTkFrame and is used to display the session in the main page.
    """ 
    def __init__(self, parent, controller : App, session_name : str):
        ctk.CTkFrame.__init__(self, parent, corner_radius=0)
        self.controller = controller
        self.pack(fill = ctk.BOTH, expand = True)
        self.session_name = session_name

        self.bread = Breadcrums(self, controller, session_name)
        self.bread.pack(side="top", fill="x")

        root_folder = Folder(self, controller, "/")
        self.folders = {"/": root_folder}
        self.curr_path = "/"

        
    def change_folder(self, path, calling_folder=None):
        """
        Change the folder in the main page to the given path
        This should be called from MainPage
        @param path: The path to the folder to be changed to
        """
        print(f"Current folder: {path}")
        if self.curr_path == path:
            return
        tofolder = None
        if path in self.folders:
            tofolder = self.folders[path]
        else:
            new_folder = Folder(self, self.controller, path)
            self.folders[path] = new_folder
            tofolder = new_folder

        self.folders[self.curr_path].pack_forget()
        self.curr_path = path

        tofolder.refresh()
        tofolder.pack(fill=ctk.BOTH, expand=True)
        tofolder.lift()
        self.bread.set_path(path)
        self.bread.lift()

    def refresh(self, folder=None):
        """
        Refresh the frame and display all updates
        """
        folder = self.folders[self.curr_path] if folder is None else self.folders[folder]
        folder.refresh()
        

@clickable
class Folder(ctk.CTkScrollableFrame):
    """
    This class represents the current folder we are in
    It contains all the files and folders that are in the current folder, the current folder, and the frame to display
    """

    def __init__(self, parent, controller : App, path):
        ctk.CTkScrollableFrame.__init__(self, parent, corner_radius=0)

        self.controller = controller
        self.path = path
        self.pack(fill = ctk.BOTH, expand = True)
        
        self.file_list : list[IconButton] = []
        self.folder_list : list[IconButton] = []
        self.session_list : list[IconButton] = []
        self.item_lists = [self.folder_list, self.file_list]

        # Make the scrollbar thinner
        self._scrollbar.configure(width=16)

    def refresh(self):
        self.pack(fill=ctk.BOTH, expand=True)
        self.controller.get_api().get_items_in_folder_async(lambda f: self.update_button_lists(f.result()), self.path)
        
    def update_button_lists(self, item_generator):
        existing_items = []
        for item in item_generator:
            item_list = self.file_list if item.get("type") == "file" else self.folder_list
            existing_items.append(item)
            new_item = None
            if item.get("type") == "file" and item not in self.file_list:
                new_item = FileButton(self, width=120, height=120, file_data=item, controller=self.controller)
            if item.get("type") == "folder" and item not in self.folder_list:
                new_item = FolderButton(self, width=120, height=120, folder_path=item.get("path"), controller=self.controller, session=self.master.master.master)
            if item.get("type") == "session" and item not in self.folder_list:
                new_item = SharedFolderButton(self, width=120, height=120, uid=item.get("uid"), is_owner=item.get("isowner"), controller=self.controller)
            if item.get("type") == "pending" and item not in self.folder_list:
                new_item = PendingSharedFolderButton(self, width=120, height=120, uid=item.get("uid"), controller=self.controller)
            if new_item is not None:
                item_list.append(new_item)
        
        for item_list in self.item_lists:
            for item in item_list:
                if item not in existing_items:
                    item_list.remove(item)
                    item.grid_forget()
                    # item.destroy()

        self._refresh()

    def _refresh(self):
        """
        Refresh the frame and display all updates
        """
        columns = 6

        # Forget all existing files and folders
        for widget in self.winfo_children():
            widget.grid_forget()

        for col in range(columns):
            self.grid_columnconfigure(col, weight=1, uniform="file_grid")
        index = 0

        for item_list in self.item_lists:
            for item in item_list:

                row = index // columns
                col = index % columns   

                item.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
                index += 1

@clickable
class SessionsFolder(Folder):
    def __init__(self, parent, controller : App, path=None):
        Folder.__init__(self, parent, controller, path)
        self.loadingpage = LoadingPage(self, controller)
        self.loaded = False
        self.loadingpage.pack(anchor=ctk.N, fill=ctk.BOTH, expand=True, padx=5, pady=3)
        self.loadingpage.start()
        self.controller.get_api().add_callback_to_sync_task(lambda: self.remove_loading())

    def remove_loading(self):
        """
        Remove the loading GIF and display the shared sessions
        """
        self.loadingpage.stop()
        self.loadingpage.pack_forget()
        self.loaded = True
        self.update_button_lists(self.controller.get_api().get_shared_folders())

    def refresh(self):
        self.pack(fill=ctk.BOTH, expand=True)
        if self.loaded:
            self.update_button_lists(self.controller.get_api().get_shared_folders())

@clickable
class SearchResultsSession(Folder):
    """
    This class represents the search results folder, it is a subclass of Folder and is used to display the search results in a separate folder.
    """
    def __init__(self, parent, controller : App, path=None):
        """
        path is unused in this class, but we need to pass it to the parent class constructor
        """
        Folder.__init__(self, parent, controller, None)
        self.controller = controller
        self.path = None
        self.query = None

    def set_query(self, query):
        """
        Set the query for the search results folder
        @param query: The query to be set
        """
        self.query = query

    def refresh(self):
        self.pack(fill=ctk.BOTH, expand=True)
        for index,_ in enumerate(self.item_lists):
            self.item_lists[index] = []
        self.controller.get_api().get_search_results_async(lambda f: self.update_button_lists(f.result()), self.query)

    def change_folder(self, path, calling_folder = None):
        """
        Change the folder in the main page to the given path
        This should be called from MainPage
        @param path: The path to the folder to be changed to
        """
        print(f"Current folder: {path}")
        self.controller.change_session(calling_folder.session.uid)

@clickable
class IconButton(ctk.CTkFrame):
    """
    This class is an abstract button class for all icons that go in MainFrame
    """
    classid = "icon"
    def __init__(self, master, width, height, icon_path, text, name, controller):
        ctk.CTkFrame.__init__(self, master, width=width, height=height)
        self.controller = controller
        self.master = master
        self.name = name
        self.file_icon = ctk.CTkImage(light_image=Image.open(icon_path), size=(60, 60))

        icon_label = ctk.CTkLabel(self, image=self.file_icon, text="")
        icon_label.pack(pady=(5, 0))

        name_label = ctk.CTkLabel(self, text=text, wraplength=90, justify="center")
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

    def __eq__(self, other):
        if isinstance(other, IconButton):
            return self.name == other.name and other.__class__ == self.__class__
        if isinstance(other, dict):
            return self.name == other.get("name") and self.__class__.classid == other.get("type")
        return False
    
    def __ne__(self, other):
        return not self.__eq__(other)

    def on_button1_click(self, event=None):
        self.controller.button_clicked(self)

    def on_double_click(self, event=None):
        self.controller.button_clicked(self)
    
    def on_button3_click(self, event=None):
        self.controller.button_clicked(self)

@clickable
class FileButton(IconButton):
    """
    This class represents a "file button"
    A file button is the frame surronding the file icon and name, so every mouse click in that area is considered as an action related to that specific file 
    """
    classid = "file"
    def __init__(self, master, width, height, file_data, controller):
        IconButton.__init__(self, master, width, height, "resources/file_icon.png", file_data["name"], file_data["name"], controller)
        self.file_data = file_data

        # Create a context menu using CTkFrame for file operations (As of now we have only download and delete)
        self.context_menu = OptionMenu(controller.container, self.controller, [
            {
                "label": "Download File",
                "color": "#3A3C41",
                "event": lambda: self.download_file_from_cloud(self.file_data)
             },
             {
                 "label": "Delete File",
                 "color": "#3A3C41",
                 "event": lambda: self.delete_file_from_cloud(self.file_data)
             }
        ])


    def download_file_from_cloud(self, file_data):
        """
        Download file from the cloud and refresh the page
        @param file_id: The id of the file to be downloaded
        """
        label = self.controller.add_message_label(f"Downloading file {file_data['name']}")

        self.controller.get_api().download_file(
            lambda f: (
                self.controller.remove_message(label),
                messagebox.showerror("Application Error", str(f.exception())) if f.exception() else None
            ),
            file_data["id"]
        )

    def delete_file_from_cloud(self, file_data):
        """
        Delete file from the cloud and refresh the page
        @param file_id: The id of the file to be deleted
        """
        file_name = file_data['name']
        desc_text = f'"{file_name}" will be permanently deleted.'
        title = "Delete This File?"
        
        def on_confirm():
            label = self.controller.add_message_label(f"Deleting file {file_name}")
            self.controller.get_api().delete_file(
            lambda f: (
                self.controller.remove_message(label),
                self.master.refresh(),
                messagebox.showerror("Application Error",str(f.exception())) if f.exception() else None
            ),
            file_data["id"]
            )
            # Immediately pop the file from the list

        self.controller.show_message_notification(desc_text, title, on_confirm)

    def open_file_from_cloud(self, file_data):
        label = self.controller.add_message_label(f"Opening file {file_data['name']}")

        self.controller.get_api().open_file(
            lambda f: (
                self.controller.remove_message(label),
                messagebox.showerror("Application Error",str(f.exception())) if f.exception() else None
            ),
            file_data["id"]
        )

    def on_button3_click(self, event=None):
        """
        When clicking on a file, open the context menu for that file, double clicking means open-close the context menu
        Click on a file close any other open context menus
        @param event: The event that triggered this function
        """
        scaling_factor = ctk.ScalingTracker.get_window_scaling(self.controller)
        if self.context_menu.context_hidden:
            self.context_menu.show_popup((event.x_root - self.context_menu.master.winfo_rootx())/scaling_factor, (event.y_root - self.context_menu.master.winfo_rooty())/scaling_factor)
        else:
           self.context_menu.hide_popup()

    def on_button1_click(self, event=None):
        super().on_button1_click(event)
    
    def on_double_click(self, event=None):
        """
        When double-clicking on a file, open the file using the `open_file` function.
        """
        super().on_double_click(event)
        try:
            print(f"Opening file: {self.file_data['name']}")
            self.open_file_from_cloud(self.file_data)
        except Exception as e:
            print(f"Error opening file: {e}")

class Popup:
    def __init__(self, controller : App):
        self.controller = controller
        self.context_hidden = True

    def show_popup(self):
        if self.context_hidden:
            self.context_hidden = False
            self.controller.set_popup(self)
            self.lift()

    def hide_popup(self):
        if not self.context_hidden:
            self.context_hidden = True
            self.controller.remove_popup(self)
    
    def lift():
        pass
    
class OptionMenu(ctk.CTkFrame, Popup):
    """
    Class to create the context menu option bar
    """
    def __init__(self, master, controller, buttons):
        """
        @param buttons list of dictionaries as such: [{"label" : str, "color": str, "event": function}]
        """
        ctk.CTkFrame.__init__(self, master, corner_radius=0, fg_color="#3A3C41")
        self.controller = controller
        self.buttons : list[ctk.CTkButton] = []
        self.context_hidden = True
        for button in buttons:
            butt = ctk.CTkButton(self, text=button["label"],
                                      command=button["event"],
                                      width=130, height=30, fg_color=button["color"])
            butt.pack(pady=5, padx=10, fill="x")
            butt.bind("<Button-1>", lambda event: self.hide_popup(), add="+")
            self.buttons.append(butt)

    def hide_popup(self):
        """
        Hide the current context menu
        """
        if not self.context_hidden:
            self.place_forget()
        Popup.hide_popup(self)
            
    
    def show_popup(self, x, y):
        """
        Display the current context menu on the selected location
        """ 
        if self.context_hidden:
            x_anchor = "w" if x < self.master.winfo_width()/2 else "e"
            # this doesn't work because of the scrollable frame
            #y_anchor = "s" if y < self.master.winfo_height()/2 else "n"
            self.place(x=x, y=y, anchor=f"n{x_anchor}")
        Popup.show_popup(self)

    def change_options(self, options : list[str]):
        for butt in self.buttons:
            butt.pack_forget()
        for butt in self.buttons:
            if butt.cget("text") in options:
                butt.pack(pady=5, padx=10, fill="x")
    
    def show_all_options(self):
        for butt in self.buttons:
            butt.pack_forget()
        for butt in self.buttons:
            butt.pack(pady=5, padx=10, fill="x")
            

class MessageNotification(ctk.CTkFrame, Popup):
    """
    This class represents a message notification popup
    """
    def __init__(self, master, controller, width=350, height=200, title="Notification", description="", on_confirm=None, on_cancel=None):
        """
        Initialize the message notification popup
        @param master: The parent widget
        @param width: Width of the popup
        @param height: Height of the popup
        @param title: Title of the popup
        @param description: Description text of the popup
        @param on_confirm: Function to call when the confirm button is clicked
        @param on_cancel: Function to call when the cancel button is clicked
        """
        ctk.CTkFrame.__init__(self, master, width=width, height=height, corner_radius=10, fg_color="#3A3C41")
        self.place(relx=0.5, rely=0.5, anchor="center")  # Center of the parent window
        self.controller = controller
        self.context_hidden = True
        # Bind a click event to the root window
        self.bind("<Button-1>", self._handle_outside_click, add="+")
        
        # Ensure the frame respects the specified width and height
        self.pack_propagate(False)  
        self.grid_propagate(False)  

        # Title
        title_label = ctk.CTkLabel(self, text=title, font=("Arial", 20, "bold"), wraplength=width - 20, justify="center")
        title_label.pack(pady=(10, 5), padx=10)

        # Description
        desc_label = ctk.CTkLabel(self, text=description, font=("Arial", 12), wraplength=width - 20, justify="center")
        desc_label.pack(pady=(5, 10), padx=10)

        # Buttons frame
        buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        buttons_frame.pack(pady=(5, 10))

        # Cancel button
        cancel_button = ctk.CTkButton(buttons_frame, text="Cancel", width=80,
                          fg_color="transparent", hover_color="gray",
                          text_color="white",
                          command=lambda: self._handle_cancel(on_cancel))
        cancel_button.grid(row=0, column=0, padx=(10, 5))

        # Confirm button
        confirm_button = ctk.CTkButton(buttons_frame, text="Confirm", width=80,
                           command=lambda: self._handle_confirm(on_confirm))
        confirm_button.grid(row=0, column=1, padx=(5, 10))

        Popup.show_popup(self)

    def _handle_confirm(self, on_confirm):
        """
        Handle the confirm button click
        @param on_confirm: Function to call when the confirm button is clicked
        """
        if on_confirm:
            on_confirm()
        self.hide_popup()

    def _handle_cancel(self, on_cancel):
        """
        Handle the cancel button click
        @param on_cancel: Function to call when the cancel button is clicked
        """
        if on_cancel:
            on_cancel()
        self.hide_popup()
    
    def _handle_outside_click(self, event):
        """
        Handle clicks outside the notification frame
        """
        # Check if the click occurred outside the notification frame
        if not self.winfo_containing(event.x_root, event.y_root) == self:
            self._handle_cancel(None)  # Close the notification

    def hide_popup(self):
        Popup.hide_popup(self)
        self.destroy()

@clickable
class FolderButton(IconButton):
    """
    This class represents a "folder button"
    A folder button is the frame surronding the folder icon and name, so every mouse click in that area is considered as an action related to that specific folder
    """
    classid = "folder"
    def __init__(self, master, width, height, folder_path, controller, session):
        self.folder_path = folder_path
        self.session = session
        name_index = folder_path.rfind("/")+1
        if len(folder_path) > name_index:
            self.folder_name = folder_path[name_index:]
        elif folder_path == "/":
            self.folder_name = "/"
        else:
            raise Exception("Invalid folder path")  
        
        IconButton.__init__(self, master, width, height, "resources/folder_icon.png", self.folder_name, self.folder_name, controller)
        self.controller = controller
        self.master = master

        # Create a context menu using CTkFrame for folder operations (As of now we don't suport these operations)
        self.context_menu = OptionMenu(self.controller.container, self.controller, [
            {
                "label": "Download Folder",
                "color": "#3A3C41",
                "event": lambda: self.download_folder()
             },
             {
                 "label": "Delete Folder",
                 "color": "#3A3C41",
                 "event": lambda: self.delete_folder_from_cloud() 
             }
        ])
    
    
    def delete_folder_from_cloud(self):
        """
        Delete folder from the cloud and refresh the page
        @param folder_path: The path of the folder to be deleted
        """
        desc_text = f'"{self.folder_path}" will be permanently deleted.'
        title = "Delete This Folder?"
        def on_confirm():
            label = self.controller.add_message_label(f"Deleting folder {self.folder_path}")
            self.controller.get_api().delete_folder(
            lambda f: (
                self.controller.remove_message(label),
                self.master.refresh(),
                messagebox.showerror("Application Error", str(f.exception())) if f.exception() else self.controller.refresh()
            ),
            self.folder_path
            )
            # Immediately pop the folder from the list

        self.controller.show_message_notification(desc_text, title, on_confirm)
    
    def download_folder(self):
        """
        Download folder from the cloud and refresh the page
        @param folder_path: The path of the folder to be downloaded
        """
        label = self.controller.add_message_label(f"Downloading folder {self.folder_path}")
        self.controller.get_api().download_folder(
            lambda f: (
                self.controller.remove_message(label),
                messagebox.showerror("Application Error", str(f.exception())) if f.exception() else self.controller.refresh()
            ),
            self.folder_path
            )

    def on_double_click(self, event=None):
        """
        When double clicking on a folder, Display the folder contents
        @param event: The event that triggered this function
        """
        super().on_double_click(event)
        self.session.change_folder(self.folder_path)
    
    def on_button3_click(self, event=None):
        scaling_factor = ctk.ScalingTracker.get_window_scaling(self.controller)
        if self.context_menu.context_hidden:
            self.context_menu.show_popup((event.x_root - self.context_menu.master.winfo_rootx())/scaling_factor, (event.y_root - self.context_menu.master.winfo_rooty())/scaling_factor)
        else:
           self.context_menu.hide_popup()
    
    def on_button1_click(self, event=None):
        super().on_button1_click(event)

@clickable
class SharedFolderButton(IconButton):
    """
    This class represents a "shared folder button"
    A shared folder button is the frame surronding the folder icon and name, so every mouse click in that area is considered as an action related to that specific folder 
    """
    classid = "session"
    def __init__(self, master, width, height, uid, is_owner, controller):

        # Get the folder name from the path
        self.uid = uid
        self.name = uid.split("$")[0]
        super().__init__(master, width, height, "resources/shared_folder_icon.png", self.name, self.uid, controller)
        self.controller = controller
        self.master = master

        self.is_owner = is_owner
        

        # Create a context menu using CTkFrame (for shared folder operations (As of now we don't suport these operations)
        if is_owner:
            menu_options = [
                {
                    "label": "Manage Permissions",
                    "color": "#3A3C41",
                    "event": lambda: self.manage_share_permissions()
                },
                {
                    "label": "Delete Share",
                    "color": "#3A3C41",
                    "event": lambda: self.delete_shared_folder()
                }
            ]
        else:
            menu_options = [
                {
                    "label": "Leave Share",
                    "color": "#2B2D2F",
                    "event": lambda: self.leave_shared_folder()
                }
            ]
        self.context_menu = OptionMenu(self.controller.container, self.controller, menu_options)


    def on_double_click(self, event=None):
        """
        When double clicking on a folder, Display the folder contents
        @param event: The event that triggered this function
        """
        # Add here the correct function
        self.controller.change_session(self.uid)
        super().on_double_click(event)
    
    def on_button1_click(self, event=None):
        super().on_button1_click(event)


    def leave_shared_folder(self):
        print("leave_share_clicked")
        desc_text = f'You will no longer can see "{self.name}".'
        title = "Are you sure you want to leave this share?"
        def on_confirm():
            label = self.controller.add_message_label(f"Leaving share {self.name}")
            self.controller.get_api().leave_shared_folder(
                lambda f: (
                    self.controller.remove_message(label),
                    self.controller.refresh(),
                    messagebox.showerror("Application Error", str(f.exception())) if f.exception() else self.controller.refresh()
                    
                ), 
                self.uid
            )
        self.controller.show_message_notification(desc_text, title, on_confirm)


    def delete_shared_folder(self):
        print("delete_share_clicked")
        folder_name = self.name.split("$")[0]
        desc_text = f'"{folder_name}" Will be permanently deleted.'
        title = "Are you sure you want to leave this share?"
        
        def on_confirm():
            label = self.controller.add_message_label(f"Deleting share {folder_name}")
            self.controller.get_api().delete_shared_folder(
                lambda f: (
                    self.controller.remove_message(label),
                    self.controller.refresh(),
                    messagebox.showerror("Application Error", str(f.exception())) if f.exception() else self.controller.refresh()
                    
                ), 
                self.uid
            )
        self.controller.show_message_notification(desc_text, title, on_confirm)

    def manage_share_permissions(self):
        new_window = ctk.CTkToplevel(self)
        new_window.title("Manage Share Permissions")
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

        # Share with header
        share_with_label = ctk.CTkLabel(scrollable_frame, text="Share with:", anchor="w", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"))
        share_with_label.grid(row=0, column=0, padx=(0, 10), pady=(20, 5), sticky="w")
        
        # Email list input
        email_frame = ctk.CTkFrame(scrollable_frame, fg_color=scrollable_frame.cget('fg_color'))  # Match background
        email_frame.grid(row=1, column=0, columnspan=2, pady=0, sticky="w")

        # List to hold email input fields
        email_inputs = []  

        # Initial email input field
        initial_email_entry = ctk.CTkEntry(email_frame, width=300)
        initial_email_entry.grid(row=1, column=0, pady=5, padx=(0, 10), sticky="w")
        email_inputs.append(initial_email_entry)

        # Function to add new email input
        def add_email_input():
            if len(email_inputs) < 5:
                new_email_entry = ctk.CTkEntry(email_frame, width=300)
                new_email_entry.grid(row=len(email_inputs) + 1, column=0, pady=5, padx=(0, 10), sticky="w")
                email_inputs.append(new_email_entry)

        # "+" button to add email inputs (styled as a small circular button)
        plus_button = ctk.CTkButton(email_frame, text="+", command=add_email_input, width=30, height=30, corner_radius=15)
        plus_button.grid(row=1, column=1, padx=10, pady=5)

        # Function to handle the creation of new share
        def add_to_exsisting_share():
            emails = [email.get() for email in email_inputs]
            parsed_emails = ", ".join(emails)
            print(f"Adding to share with emails: {emails}")
            label = self.controller.add_message_label(f"Adding {parsed_emails} to share")
            # Call the API with the final array
            self.controller.get_api().add_users_to_share(
                    lambda f: (
                            self.controller.remove_message(label)
                        ),
                        self.uid,
                        emails
                    )
            # Close the new window
            new_window.destroy()

        # Create new share button (this now does both actions: create share and close the window)
        add_to_share_button = ctk.CTkButton(scrollable_frame, text="Share", command=add_to_exsisting_share, width=80, height=37, corner_radius=15)
        add_to_share_button.grid(row=2, column=0, pady=20, sticky="w")

        # Already shared emails
        shared_with_label = ctk.CTkLabel(scrollable_frame, text="Already shared with:", anchor="w", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"))
        shared_with_label.grid(row=3, column=0, padx=(0, 10), pady=(10, 5), sticky="w")

        # List of emails already shared
        self.shared_emails = self.controller.get_api().get_shared_emails(self.uid)  # Fetch shared emails from API
         

        def remove_email(display_email, email):
            """
            Function to remove an email from the shared list
            """
            
            for widget in scrollable_frame.winfo_children():
                if hasattr(widget, 'custom_id') and widget.custom_id == display_email and isinstance(widget, ctk.CTkButton):
                    widget.configure(state="disabled")

            desc_text = f'"Remove User From Share"'
            title = f"Remove {display_email} from share?"
            def on_confirm():
                label = self.controller.add_message_label(f"Removing {display_email} from share")
                self.controller.get_api().revoke_user_from_share(
                    lambda f, display_email=display_email: (
                            remove_email_and_rearrange(display_email) if not f.exception() else messagebox.showerror("Error", f"Failed to revoke user: {f.exception()}"),
                            self.controller.remove_message(label)
                        ),
                        self.uid,
                        email
                    )
                # Immediately pop the folder from the list
            MessageNotification(new_window, self.controller, title=title, description=desc_text, on_confirm=on_confirm)

        def remove_email_and_rearrange(display_email):
            # Remove the relevant email label and remove button using custom_id
            for widget in scrollable_frame.winfo_children():
                if hasattr(widget, 'custom_id') and widget.custom_id == display_email:
                    if widget.winfo_exists():  # Check if the widget still exists
                        widget.destroy()

            # Remove the email from the shared list
            self.shared_emails = [email for email in self.shared_emails if list(email.values())[0] != display_email]

            # Rearrange the remaining email labels and buttons
            scrollable_frame.update_idletasks()  # Ensure the frame is updated after widget removal


        # Display each email with alignment and a "Remove" button
        if self.shared_emails:
            for idx, email in enumerate(self.shared_emails):
                # Display email aligned to the left
                display_email = list(email.values())[0]  # Get the value of the first element in the dictionary
                email_label = ctk.CTkLabel(scrollable_frame, text=display_email, anchor="w")
                email_label.grid(row=idx + 4, column=0, sticky="w")
                email_label.custom_id = display_email

                # Add "Remove" button aligned to the right
                remove_button = ctk.CTkButton(scrollable_frame, text="Remove", 
                                command=lambda email=email, display_email=display_email: remove_email(display_email, email), 
                                width=80, height=37, corner_radius=15)
                remove_button.grid(row=idx + 4, column=1, padx=100, sticky="e")
                remove_button.custom_id = display_email
        
        

        # Adjust the scrollbar to make it thinner (no slider_length argument)
        new_window.after(100, lambda: scrollable_frame._scrollbar.configure(width=8))  # Adjust the width of the scrollbar

    def on_button3_click(self, event=None):
        scaling_factor = ctk.ScalingTracker.get_window_scaling(self.controller)
        if self.context_menu.context_hidden:
            self.context_menu.show_popup((event.x_root - self.context_menu.master.winfo_rootx())/scaling_factor, (event.y_root - self.context_menu.master.winfo_rooty())/scaling_factor)
        else:
           self.context_menu.hide_popup()

@clickable
class PendingSharedFolderButton(IconButton):
    """
    This class represents a "pending shared folder button"
    A pending shared folder button is the frame surronding the folder icon and name, so every mouse click in that area is considered as an action related to that specific folder 
    """
    classid = "pending"
    def __init__(self, master, width, height, uid, controller):
        self.uid = uid
        self.name = uid.split("$")[0]
        super().__init__(master, width, height, "resources/folder_icon_pending.png", self.name, self.uid, controller)
        self.controller = controller
        self.master = master

        # Create a context menu using CTkFrame (for shared folder operations (As of now we don't suport these operations)
        menu_options = [
            {
                "label": "Decline Share",
                "color": "#3A3C41",
                "event": lambda: self.leave_shared_folder()
            }
        ]
        self.context_menu = OptionMenu(self.controller.container, self.controller, menu_options)

    def leave_shared_folder(self):
        print("leave_share_clicked")
        label = self.controller.add_message_label(f"Decline share {self.name}")
        # Call a new function with the folder and emails (replace this with your logic)
        self.controller.get_api().leave_shared_folder(lambda f: (self.controller.refresh(), self.controller.remove_message(label)), self.uid)

    def on_button3_click(self, event=None):
        scaling_factor = ctk.ScalingTracker.get_window_scaling(self.controller)
        if self.context_menu.context_hidden:
            self.context_menu.show_popup((event.x_root - self.context_menu.master.winfo_rootx())/scaling_factor, (event.y_root - self.context_menu.master.winfo_rooty())/scaling_factor)
        else:
           self.context_menu.hide_popup()