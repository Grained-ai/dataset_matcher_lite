from abc import ABC
from typing import TypeVar, Type, Dict

T = TypeVar('T', bound='Singleton')


class Singleton(ABC):
    _instances: Dict[Type[T], T] = {}

    def __new__(cls: Type[T], *args, **kwargs) -> T:
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__new__(cls)
        return cls._instances[cls]
