import os
import shutil

from .Split import Split

class NoSplit(Split):
    def split_file(self, file, num_parts) -> str:
        for i in range(0,num_parts-2):
            shutil.copy(file, file + str(i))

    def merge_parts(self, folder) -> str:
        return os.path.join(folder, os.listdir(folder)[0])
    
    def get_name(self):
        return "No"