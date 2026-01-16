class MetadataObject:
    def __init__(
        self,
        title: str,
        resolution: str,
        description="",
        language="ru",
        mode="live",
        cursor=True,
        fps=30
    ):
        self.title = title
        self.resolution = resolution
        self.description = description
        self.language = language
        self.mode = mode
        self.cursor = cursor
        self.fps = fps