from pathlib import Path

import pytest
from pytest import MonkeyPatch

from eagleeye.discovery import match_dir


def test_match_dir_happy_path(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path.resolve()
    monkeypatch.setattr("eagleeye.discovery.LOGS", root)
    result = match_dir("2026cacac", "qm1")
    assert result == root / "2026cacac" / "qm1"


def test_match_dir_rejects_traversal(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("eagleeye.discovery.LOGS", tmp_path.resolve())
    with pytest.raises(ValueError):
        match_dir("../../etc", "passwd")


def test_match_dir_rejects_absolute(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("eagleeye.discovery.LOGS", tmp_path.resolve())
    with pytest.raises(ValueError):
        match_dir("/etc", "passwd")
