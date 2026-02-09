"""TOML string escaping utilities.

Provides a single, spec-complete escape function for TOML basic strings.
All code that writes TOML values by hand (TUI persistence, WaiverGenerator)
should use this module instead of rolling its own escaping.
"""

from __future__ import annotations

import re

# Control characters that need \uXXXX escaping: U+0000-U+001F and U+007F,
# excluding those with dedicated escape sequences (\b \t \n \f \r).
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x07\x0b\x0e-\x1f\x7f]")


def escape_toml_basic_string(value: str) -> str:
    """Escape a string for safe embedding in a TOML basic string.

    Handles all escapes required by the TOML specification for basic
    strings (delimited by double quotes). The escapes are applied in the
    correct order to avoid double-escaping.

    Order of escapes:
        1. ``\\``  -> ``\\\\``   (backslash -- must be first)
        2. ``"``   -> ``\\"``
        3. U+0008  -> ``\\b``    (backspace)
        4. U+0009  -> ``\\t``    (tab)
        5. U+000A  -> ``\\n``    (newline)
        6. U+000C  -> ``\\f``    (form feed)
        7. U+000D  -> ``\\r``    (carriage return)
        8. Remaining control characters (U+0000-U+001F, U+007F) -> ``\\uXXXX``

    Args:
        value: The raw Python string to escape.

    Returns:
        An escaped string that can be placed between double quotes in a
        TOML document and parsed back to the original value.
    """
    # 1. Backslash (must be first to avoid escaping escape sequences)
    result = value.replace("\\", "\\\\")
    # 2. Double quote
    result = result.replace('"', '\\"')
    # 3. Backspace
    result = result.replace("\b", "\\b")
    # 4. Tab
    result = result.replace("\t", "\\t")
    # 5. Newline
    result = result.replace("\n", "\\n")
    # 6. Form feed
    result = result.replace("\f", "\\f")
    # 7. Carriage return
    result = result.replace("\r", "\\r")
    # 8. Remaining control characters -> \uXXXX
    result = _CONTROL_CHAR_RE.sub(lambda m: f"\\u{ord(m.group()):04X}", result)

    return result
