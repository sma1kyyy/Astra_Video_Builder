from abc import ABC
from typing import Any, Dict

class ComponentObject(ABC):
    """базовый класс для всех объектов сцены/видео"""
    
    def __init__(self, **kwargs):
        # автоматически заполняем все атрибуты из kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def __repr__(self):
        # показывает имя класса и основные поля
        attrs = {k: v for k, v in self.__dict__.items() 
                if not k.startswith('_')}
        return f"<{self.__class__.__name__}: {attrs}>"
    
    def to_dict(self) -> Dict[str, Any]:
        """сериализация в словарь для отладки"""
        return self.__dict__.copy()
