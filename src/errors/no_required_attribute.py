class NoRequiredAttribute(Exception):
    """Исключение для обработки ситуаций, в которых в передаваемом yaml-скрипте отсутствует один из обязательных параметров."""
    def __init__(self, attr: str | None):
        """В attr передаётся название пропущенного аттрибута."""
        extra_info = ""
        if attr:
            extra_info = f"Missing field: {attr}"
        super().__init__("A required attribute is missing in YAML-script. " + extra_info)