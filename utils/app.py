import customtkinter as ctk
import tkinter as tk
from CTkListbox import CTkListbox  # Ensure CTkListbox is installed
import Gateway

class App():
    """
    This class creates the UI features and the program main window.
    """
    
    def __init__(self, gateway):
        self.root = ctk.CTk()
        self.root.title("EncryptoSphere")
        self.root.geometry("400x300")
        self.api = gateway
        
    def run(self):
        self.login_window()
        self.root.mainloop()
        
    def login_window(self):
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True)
        self.message = ctk.CTkLabel(self.main_frame, text="Enter your Email Address:")
        self.message.pack(pady=20)
        self.entry = ctk.CTkEntry(self.main_frame, placeholder_text="Example@gmail.com")
        self.entry.pack(pady=10)
        self.submit_button = ctk.CTkButton(self.main_frame, text="Submit", command=self.__handle_login)
        self.submit_button.pack(pady=10)

    def __handle_login(self):
        email = self.entry.get()
        result = self.api.authenticate(email)
        print(result)
        if not result:
            for widget in self.main_frame.winfo_children():
                widget.destroy()
            self.__show_error("Error While connecting to the Cloud", self.login_window)
        else:
            for widget in self.main_frame.winfo_children():
                widget.destroy() 
            self.main_window()
    

    def main_window(self):
        files_list = self.api.get_files()

    def __show_error(self, error_message, func):
        self.error_label = ctk.CTkLabel(self.main_frame, text=error_message)
        self.error_label.pack(pady=20)
        # Add a button to go back and retry
        self.retry_button = ctk.CTkButton(self.main_frame, text="Retry", command=func)
        self.retry_button.pack(pady=10)


# Set up the main application window
def run_app():
    app = ctk.CTk()
    app.geometry("400x300")
    app.title("File Manager")

    # Create a frame to hold the listbox and buttons
    frame = ctk.CTkFrame(app)
    frame.pack(pady=20, padx=20, fill="both", expand=True)

    # Create a listbox to display files
    file_listbox = CTkListbox(frame, height=10)
    file_listbox.pack(pady=10, padx=10, fill="both", expand=True)

    # Populate the listbox with a static list of files
    files = ["file1.txt", "file2.txt", "file3.txt"]  # Replace with your actual file list
    for file in files:
        file_listbox.insert(tk.END, file)

    # Function to handle file selection
    def on_file_select(event):
        selected_file = file_listbox.get(file_listbox.curselection())
        print(f"Selected file: {selected_file}")
        # Implement further actions based on the selected file

    # Bind the listbox selection event
    file_listbox.bind("<<ListboxSelect>>", on_file_select)

    
    # Function to handle file download
    def download_file():
        selected_file = file_listbox.get(file_listbox.curselection())
        print(f"Downloading file: {selected_file}")
        # Implement the download functionality here

    # Function to handle file upload
    def upload_file():
        print("Uploading file...")
        # Implement the upload functionality here
    
    # Create and place the "Download" button
    download_button = ctk.CTkButton(frame, text="Download", command=download_file)
    download_button.pack(pady=5, padx=10, fill="x")

    # Create and place the "Upload" button
    upload_button = ctk.CTkButton(frame, text="Upload", command=upload_file)
    upload_button.pack(pady=5, padx=10, fill="x")

    # Run the application
    app.mainloop()

