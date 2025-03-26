from abc import ABC, abstractmethod

class Split(ABC):
    @abstractmethod
    def split(self, data : bytes, num_parts : int) -> str:
        """
        Splits the file into num_parts
        @return the folder path
        """
        pass

    @abstractmethod
    def merge_parts(self, data : bytes) -> str:
        """
        Merges parts using the split algorithm
        @param data the parts of the data in an array
        @return the merged file path
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Returns the signature of the splitting algorithm
        Used to write to the file descriptor
        """
        pass




