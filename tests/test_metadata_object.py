import pytest
from pydantic import ValidationError

from core.schemas.metadata_object import MetadataObject


class TestMetadataDefaults:
    def test_minimal_required(self):
        m = MetadataObject(title="X", resolution="1920x1080")
        assert m.mode == "live"
        assert m.browser == "chrome"
        assert m.cursor is False
        assert m.fps == 30
        assert m.save_files is False
        assert m.language == "ru"

    def test_browser_firefox(self):
        m = MetadataObject(title="X", resolution="1920x1080", browser="firefox")
        assert m.browser == "firefox"

    def test_invalid_browser(self):
        with pytest.raises(ValidationError):
            MetadataObject(title="X", resolution="1920x1080", browser="safari")

    def test_invalid_resolution(self):
        with pytest.raises(ValidationError):
            MetadataObject(title="X", resolution="HD")

    def test_invalid_title(self):
        with pytest.raises(ValidationError):
            MetadataObject(title="bad title with spaces!", resolution="1920x1080")

    def test_save_files_true(self):
        m = MetadataObject(title="X", resolution="1920x1080", save_files=True)
        assert m.save_files is True

    def test_zero_fps_rejected(self):
        with pytest.raises(ValidationError):
            MetadataObject(title="X", resolution="1920x1080", fps=0)
