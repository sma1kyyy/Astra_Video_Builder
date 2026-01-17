class NoValue(Exception):
    """Исключение для обработки ситуаций, в которых передаётся пустой вложенный параметр."""
    def __init__(self, attr: str | None = None):
        """В attr передаётся название пустого вложенного параметра."""
        extra_info = ""
        if attr:
            extra_info = f"Empty object: {attr}"
        super().__init__("Object must have attributes inside. " + extra_info)