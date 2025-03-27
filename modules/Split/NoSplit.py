import os
import tempfile

from .Split import Split

class NoSplit(Split):
    def split(self, data, clouds_num) -> str:
        ret = []
        for _ in range(clouds_num):
            ret.append([data])  # Wrap data inside a list
        return ret

    def merge_parts(self, data, clouds_num) -> str:
        return data[0]
    
    def get_name(self):
        return "No"