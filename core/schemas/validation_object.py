from requests import get

class Valid:
    action_type = []

    @classmethod
    def validate_url(url: str):
        """
        Проверяет корректность URL
        """
        try:
            get(URL)
            return True
        except BaseException:
            return False

    @classmethod
    def validate_selector(selector: str):
        """
        Проверяет корректность selector
        """
        return True