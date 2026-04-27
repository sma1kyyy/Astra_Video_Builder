import os
from pathlib import Path

import pytest

from web.backend.app.jobs import CeleryJobRegistry, list_output_files, public_status


def test_public_status_mapping():
    assert public_status("PENDING") == "queued"
    assert public_status("RECEIVED") == "queued"
    assert public_status("STARTED") == "running"
    assert public_status("SUCCESS") == "done"
    assert public_status("FAILURE") == "failed"
    assert public_status("REVOKED") == "cancelled"
    assert public_status("WEIRD") == "weird"


def test_registry_roundtrip(tmp_path):
    reg = CeleryJobRegistry(tmp_path)
    reg.add("abc-123", "/tmp/script.yaml", "/tmp/out")
    record = reg.get("abc-123")
    assert record["job_id"] == "abc-123"
    assert record["script_path"] == "/tmp/script.yaml"
    assert record["output_dir"] == "/tmp/out"
    assert "created_at" in record


def test_registry_list_sorted_by_created_at(tmp_path):
    reg = CeleryJobRegistry(tmp_path)
    reg.add("first", "/s1", "/o1")
    reg.add("second", "/s2", "/o2")
    items = reg.list()
    assert [i["job_id"] for i in items[:2]] == ["second", "first"] or \
           [i["job_id"] for i in items[:2]] == ["first", "second"]
    assert {i["job_id"] for i in items} == {"first", "second"}


def test_registry_get_unknown_returns_none(tmp_path):
    reg = CeleryJobRegistry(tmp_path)
    assert reg.get("nope") is None


def test_registry_sanitizes_dangerous_id(tmp_path):
    reg = CeleryJobRegistry(tmp_path)
    reg.add("../../etc/passwd", "/s", "/o")
    files = list(tmp_path.iterdir())
    assert all("/" not in f.name for f in files)
    assert all(f.parent == tmp_path for f in files)


def test_list_output_files_empty(tmp_path):
    assert list_output_files(str(tmp_path)) == []


def test_list_output_files_returns_only_files(tmp_path):
    (tmp_path / "video.mp4").write_bytes(b"x")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "ignored.txt").write_text("x")
    files = list_output_files(str(tmp_path))
    assert files == ["video.mp4"]


def test_list_output_files_handles_missing_dir():
    assert list_output_files("/no/such/path/xyz") == []
