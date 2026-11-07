"""Tests for the glob translator."""

from __future__ import annotations

import re

import pytest

from sawmill.utils.globs import glob_match, glob_to_regex


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("build/*.log", "build/a.log", True),
        ("build/*.log", "build/x/a.log", False),
        ("**/ip/snps/**/*.v", "ip/snps/a.v", True),
        ("**/ip/snps/**/*.v", "src/ip/snps/x/y/b.v", True),
        ("**/ip/snps/**/*.v", "ip/other/a.v", False),
        ("**/x.v", "x.v", True),
        ("**/x.v", "a/b/x.v", True),
        ("a?c", "abc", True),
        ("a?c", "a/c", False),
        ("a?c", "ac", False),
        ("job_[0-9]", "job_3", True),
        ("job_[0-9]", "job_x", False),
        ("a.b", "axb", False),
        ("a.b", "a.b", True),
        ("a+b", "a+b", True),
        ("a+b", "aab", False),
        ("job_*", "build/job_3/vivado.log", False),
        ("/abs/**/*.v", "/abs/x/y.v", True),
    ],
)
def test_glob_match(pattern: str, path: str, expected: bool) -> None:
    assert glob_match(pattern, path) is expected


def test_glob_to_regex_compiled_and_deterministic() -> None:
    a = glob_to_regex("**/ip/*.v")
    b = glob_to_regex("**/ip/*.v")
    assert isinstance(a, re.Pattern)
    assert a.pattern == b.pattern
