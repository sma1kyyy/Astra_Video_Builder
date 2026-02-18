class IncorrectValue(Exception):
    """Исключение для обработки ситуаций, в которых в передаваемом yaml-скрипте значения неправильные."""
    def __init__(self, attr: str | None = None):
        """В attr передаётся неверное значение."""
        extra_info = ""
        if attr:
            extra_info = f"Value there: {attr}"
        super().__init__("Incorrect value. " + extra_info)