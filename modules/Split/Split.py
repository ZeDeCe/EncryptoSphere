from abc import ABC, abstractmethod

class Split(ABC):
    @staticmethod
    def get_class(sig):
        for cls in Split.__subclasses__():
            if cls.get_name() == sig:
                return cls
    
    def __init__(self):
        """
        Change copies_per_cloud according to the amount of copies there should be per cloud
        """
        self.copies_per_cloud = 1
        self.min_parts = 1
        self.min_clouds = 1

    @abstractmethod
    def split(self, data : bytes, clouds_num : int) -> str:
        """
        Splits the file into num_parts
        @return the folder path
        """
        pass

    @abstractmethod
    def merge_parts(self, data : bytes, clouds_num : int) -> bytes:
        """
        Merges parts using the split algorithm
        @param data the parts of the data in an array
        @return the merged file bytes
        """
        pass
    def copy(self):
        return self.__class__()
    
    @staticmethod
    @abstractmethod
    def get_name(self) -> str:
        """
        Returns the signature of the splitting algorithm
        Used to write to the metadata file
        """
        pass

    @staticmethod
    def get_classes() -> str:
        """
        Returns a list of all the split classes
        """
        return Split.__subclasses__()


