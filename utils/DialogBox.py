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
    

def error_dialog(title: str, message: str):
    """
    Displays an error dialog box with a title and message.
    No input field is provided. Runs in a separate thread to avoid blocking.
    """
    def show_dialog():
        def close_dialog():
            dialog.destroy()

        # Create the dialog window
        dialog = ctk.CTk()
        dialog.title(title)

        # Update idletasks to calculate the window's size
        dialog.update_idletasks()

        # Get screen dimensions
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()

        # Set the dialog's size
        dialog.geometry("400x200")

        # Get the dialog's current size
        dialog_width = 400  # Fixed width
        dialog_height = 200  # Fixed height

        # Calculate the position to center the dialog on the screen
        position_top = (screen_height // 2) - (dialog_height // 2)
        position_left = (screen_width // 2) - (dialog_width // 2)

        # Set the position without altering the size
        dialog.geometry(f"400x200+{position_left}+{position_top}")

        # Ensure the dialog stays on top
        dialog.attributes("-topmost", True)

        # Add a label for the error message
        label = ctk.CTkLabel(dialog, text=message, wraplength=350, justify="center")
        label.pack(pady=20)

        # Add a close button
        close_button = ctk.CTkButton(dialog, text="Close", command=close_dialog)
        close_button.pack(pady=10)

        # Start the event loop to display the dialog
        dialog.mainloop()

    # Run the dialog in a separate thread
    threading.Thread(target=show_dialog, daemon=True).start()