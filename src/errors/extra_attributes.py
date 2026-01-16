class ExtraAttributes(Exception):
    """Исключение для обработки ситуаций, в которых в передаваемом yaml-скрипте имеются параметры, которых быть не должно."""
    def __init__(self, attr: str | None):
        """В attr передаётся название лишнего аттрибута."""
        extra_info = ""
        if attr:
            extra_info = f"Extra field: {attr}"
        super().__init__("An extra attribute is passed in the yaml script. " + extra_info)