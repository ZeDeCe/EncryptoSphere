import os
import tempfile

from .Split import Split

class NoSplit(Split):
    def split(self, data, num_parts) -> str:
        ret = []
        for i in range(0,num_parts):
            ret.append(data)
        return ret

    def merge_parts(self, data) -> str:
        return data[0]
    
    def get_name(self):
        return "No"