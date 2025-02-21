import customtkinter

#Implement gui dialogbox
def input_dialog(title, text):
    dialog = customtkinter.CTkInputDialog(text=text, title=title)
    return dialog.get_input()
    
    