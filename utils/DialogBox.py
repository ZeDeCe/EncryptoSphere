import customtkinter as ctk
import threading


#Implement gui dialogbox
def input_dialog(title, text):
    # Create the input dialog
    dialog = ctk.CTkInputDialog(text=text, title=title)
    
    # Update idletasks to calculate the window's size
    dialog.update_idletasks()
    
    # Get screen dimensions
    screen_width = dialog.winfo_screenwidth()
    screen_height = dialog.winfo_screenheight()
    
    # Get the dialog's current size
    dialog_width = dialog.winfo_width()
    dialog_height = dialog.winfo_height()
    
    # Calculate the position to center the dialog on the screen
    position_top = (screen_height // 2) - (dialog_height // 2)
    position_left = (screen_width // 2) - (dialog_width // 2)
    
    # Set the position without altering the size
    dialog.geometry(f"+{position_left}+{position_top}")
    
    # Ensure the dialog stays on top
    dialog.attributes("-topmost", True)
    
    # Return the input received from the dialog
    return dialog.get_input()
    