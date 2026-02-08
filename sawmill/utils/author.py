"""Author discovery utility for sawmill.

Discovers the author identity from environment or git config,
used to pre-fill the author field in waiver creation.
"""

import os
import subprocess


def discover_author() -> str:
    """Discover author from env var or git config.

    Checks in order:
    1. SAWMILL_AUTHOR environment variable
    2. git config user.email
    3. git config user.name
    4. Empty string (user must fill in)

    Returns:
        The discovered author string, or empty string if not found.
    """
    # 1. Environment variable
    env_author = os.environ.get("SAWMILL_AUTHOR")
    if env_author:
        return env_author

    # 2. git config user.email
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # 3. git config user.name
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # 4. Empty string
    return ""
