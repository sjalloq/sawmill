"""Glob to regex translation for rule ``file`` and ``logs`` keys."""

from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=1024)
def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a glob into a compiled regex anchored at both ends.

    ``**`` matches any characters including ``/`` (``**/`` also matches an
    empty prefix), ``*`` any run of non-``/`` characters, ``?`` one
    non-``/`` character and ``[...]`` classes pass through.
    """
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            end = pattern.find("]", i + 2 if pattern.startswith("[!", i) else i + 1)
            if end == -1:
                out.append(re.escape(c))
                i += 1
            else:
                body = pattern[i + 1 : end]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                i = end + 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$", re.DOTALL)


def glob_match(pattern: str, path: str) -> bool:
    """Return True if POSIX ``path`` fully matches glob ``pattern``."""
    return glob_to_regex(pattern).match(path) is not None
