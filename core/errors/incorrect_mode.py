class IncorrectMode(Exception):
    """Исключение для обработки ситуаций, в которых в передаваемом yaml-скрипте в metadata неправильный режим."""
    def __init__(self, attr: str | None = None):
        """В attr передаётся название, переданное в mode в metadata."""
        extra_info = ""
        if attr:
            extra_info = f"Value there: {attr}"
        super().__init__("Incorrect mode value at metadata field. Can be 'live' or 'screenshot'. " + extra_info)