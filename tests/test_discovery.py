from pathlib import Path

import pytest
from pytest import MonkeyPatch

from eagleeye.discovery import find_root, match_dir, resolve_logs


def test_find_root_with_custom_marker(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    '''
    affirmatively tests _find_root by placing a marker in the tmp_path directory. it then creates
    an arbitrary filepath for config.py and asserts the _find_root traversal lands at tmp_path.
    '''
    (tmp_path / "MARKER").touch()
    fake_file = tmp_path / "a" / "b" / "discovery.py"
    fake_file.parent.mkdir(parents=True)
    monkeypatch.setattr("eagleeye.discovery.__file__", str(fake_file))
    assert find_root(marker="MARKER") == tmp_path

def test_find_root_raises_when_marker_absent(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    '''
    negatively tests _find_root by creating arbitrary filepath for config.py and checking that
    _find_root traversal correctly raises a runtime error when looking for a missing marker.
    '''
    fake_file = tmp_path / "deep" / "nested" / "discovery.py"
    fake_file.parent.mkdir(parents=True)
    monkeypatch.setattr("eagleeye.discovery.__file__", str(fake_file))
    with pytest.raises(RuntimeError):
        find_root(marker="mise.toml")

def test_resolve_logs_skips_find_root_when_env_set(monkeypatch: MonkeyPatch) -> None:
    '''
    affirmatievly tests that _resolve_logs does not call _find_root when env variable is set
    '''
    monkeypatch.setenv("EAGLEEYE_LOGS", "/custom/logs")

    def boom() -> None:
        raise AssertionError("_find_root should not be called when env var is set")

    monkeypatch.setattr("eagleeye.discovery.find_root", boom)
    assert resolve_logs() == Path("/custom/logs")

def test_resolve_logs_falls_back(monkeypatch: MonkeyPatch) -> None:
    '''
    affirmatively tests that _resolve_logs falls back to {root}/logs when env variable isn't set
    '''
    monkeypatch.delenv("EAGLEEYE_LOGS", raising=False)
    assert resolve_logs().name == "logs"

def test_match_dir_happy_path(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path.resolve()
    monkeypatch.setattr("eagleeye.discovery._LOGS", root)
    result = match_dir("2026cacac", "qm1")
    assert result == root / "2026cacac" / "qm1"


def test_match_dir_rejects_traversal(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("eagleeye.discovery._LOGS", tmp_path.resolve())
    with pytest.raises(ValueError):
        match_dir("../../etc", "passwd")


def test_match_dir_rejects_absolute(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("eagleeye.discovery._LOGS", tmp_path.resolve())
    with pytest.raises(ValueError):
        match_dir("/etc", "passwd")
