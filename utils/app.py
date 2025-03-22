import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from PIL import Image

class App(ctk.CTk):
    """
    This class creates the UI features and the program main window.
    """
    
    def __init__(self, gateway):
        ctk.CTk.__init__(self)
        self.title("EncryptoSphere")
        self.geometry("650x400")
        self.api = gateway
        
        # creating a container for the frames
        container = ctk.CTkFrame(self)
        container.pack(side="top", fill="both", expand=True)
        
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        
        # initializing frames to an empty dictionary
        self.frames = {} 
        
        # creating the frames
        for F in (LoginPage, MainPage):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        self.show_frame(LoginPage)
    
    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()

    def get_api(self):
        return self.api


# LoginPage: Where user enters email and authenticates
class LoginPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        ctk.CTkFrame.__init__(self, parent)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3, 4, 5), weight=1)
        
        label = ctk.CTkLabel(self, text="Login Page", font=("Verdana", 35))
        label.grid(row=0, column=0, padx=10, pady=10, sticky="n")
        
        self.message = ctk.CTkLabel(self, text="Enter your Email Address:")
        self.message.grid(row=1, column=0, padx=10, pady=10, sticky="n")
        
        self.entry = ctk.CTkEntry(self, placeholder_text="Example@gmail.com")
        self.entry.grid(row=2, column=0, padx=10, pady=10, sticky="n")
        
        self.submit_button = ctk.CTkButton(self, text="Submit", command=self.__handle_login)
        self.submit_button.grid(row=3, column=0, padx=10, pady=10, sticky="n")
        
        self.controller = controller

    def __handle_login(self):
        email = self.entry.get()
        result = self.controller.get_api().authenticate(email)
        print(result)
        
        if not result:
            self.__show_error("Error While connecting to the Cloud", self.controller.show_frame(LoginPage))
        else:
            self.controller.show_frame(MainPage)
    
    def __show_error(self, error_message, func):
        self.error_label = ctk.CTkLabel(self, text=error_message)
        self.error_label.grid(row=4, column=0, pady=20, sticky="n")
        
        self.retry_button = ctk.CTkButton(self, text="Retry", command=func)
        self.retry_button.grid(row=5, column=0, pady=10, sticky="n")


# MainPage: The main page that shows files after successful login
class MainPage(ctk.CTkFrame):
    def __init__(self, parent, controller):
        ctk.CTkFrame.__init__(self, parent)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        label = ctk.CTkLabel(self, text="My Files", font=("Verdana", 25))
        label.grid(row=0, column=0, padx=10, pady=10, sticky="n")
        
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=1, column=0, padx=10, pady=10)
        self.main_frame.place(relx=0.5, rely=0.5, anchor=ctk.CENTER)
        
        # Simulating file list
        file_list = ["My file.txt", "Very_Long_File_Name_Example.pdf", "Image.png", "Script.py",
              "Another_Document.docx", "Notes.txt", "Report_2024.xlsx", "Presentation.pptx"]
        
        file_icon = ctk.CTkImage(light_image=Image.open("resources/file_icon.png"), size=(40, 40))  
        columns = 6  
        cell_size = 120

        for col in range(columns):
            self.main_frame.grid_columnconfigure(col, weight=1, uniform="file_grid")


        for i, file_name in enumerate(file_list):
            row = i // columns  
            col = i % columns   

            file_frame = ctk.CTkFrame(self.main_frame, width=cell_size, height=cell_size)
            file_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            icon_label = ctk.CTkLabel(file_frame, image=file_icon, text="")
            icon_label.pack(pady=(5, 0))

            name_label = ctk.CTkLabel(file_frame, text=file_name, font=("Arial", 9), wraplength=90, justify="center")
            name_label.pack(pady=(0, 5))

            file_frame.bind("<Button-1>", lambda e, fname=file_name: self.on_file_click(fname, e))
            icon_label.bind("<Button-1>", lambda e, fname=file_name: self.on_file_click(fname, e))
            name_label.bind("<Button-1>", lambda e, fname=file_name: self.on_file_click(fname, e))
        
        self.controller = controller

    def on_file_click(self, file_name, event=None):
        print(f"File clicked: {file_name}")

        # Remove any existing menu first
        if hasattr(self, "context_menu"):
            self.context_menu.destroy()

        # Create a context menu using CTkFrame
        self.context_menu = ctk.CTkFrame(self, corner_radius=5, fg_color="gray25")
        self.context_menu.place(x=event.x_root - self.winfo_rootx(), y=event.y_root - self.winfo_rooty())

        # "Delete File" Button
        delete_button = ctk.CTkButton(self.context_menu, text="Delete File",
                                      command=lambda: self.controller.get_api().delete_file(file_name),
                                      width=120, height=30, fg_color="red")
        delete_button.pack(pady=5, padx=10)

        # "Download File" Button
        download_button = ctk.CTkButton(self.context_menu, text="Download File",
                                        command=lambda: self.controller.get_api().download_file(file_name),
                                        width=120, height=30)
        download_button.pack(pady=5, padx=10)

        # Auto-close menu when clicking elsewhere
        self.bind("<Button-1>", lambda event: self.context_menu.destroy(), add="+")

