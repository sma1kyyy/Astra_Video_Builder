class ObjectIdIsntValid(Exception):
    """Исключение для обработки ситуаций, в которых в параметре scenes названия объектов неправильные."""
    def __init__(self, attr: str | None):
        """В attr передаётся название неправильной сцены."""
        extra_info = ""
        if attr:
            extra_info = f"Wrong object id: {attr}"
        super().__init__("Object ID must be a number. " + extra_info)