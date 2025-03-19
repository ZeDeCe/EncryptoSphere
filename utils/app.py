import customtkinter as ctk
import tkinter as tk
from CTkListbox import CTkListbox  # Ensure CTkListbox is installed

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

run_app()