"""Unit tests for medrisk_inference.utils."""

from __future__ import annotations

import pytest

from medrisk_inference.utils import sanitize_filename


def test_none_filename_returns_none() -> None:
    assert sanitize_filename(None) is None


def test_empty_filename_returns_none() -> None:
    assert sanitize_filename("") is None


def test_plain_filename_is_kept() -> None:
    assert sanitize_filename("biopsy_patch.png") == "biopsy_patch.png"


@pytest.mark.parametrize(
    ("raw", "expected_basename"),
    [
        ("../../etc/passwd", "passwd"),
        ("/etc/passwd", "passwd"),
        ("C:\\Windows\\System32\\evil.exe", "evil.exe"),
        ("a/b/c/d.png", "d.png"),
    ],
)
def test_path_components_are_stripped(raw: str, expected_basename: str) -> None:
    result = sanitize_filename(raw)
    assert result == expected_basename
    assert "/" not in (result or "")
    assert "\\" not in (result or "")


def test_control_characters_are_stripped() -> None:
    result = sanitize_filename("evil\x00name\x1f.png")
    assert result == "evilname.png"


def test_overlong_filename_is_truncated() -> None:
    result = sanitize_filename("a" * 500 + ".png")
    assert result is not None
    assert len(result) <= 128


def test_filename_that_is_only_path_separators_returns_none() -> None:
    assert sanitize_filename("../../") is None
