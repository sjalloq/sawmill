"""Git repository utilities for sawmill.

This module provides functions for detecting and working with git repositories.
"""

import os
from pathlib import Path
from typing import Optional


def find_git_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find the root directory of a git repository.

    Walks up from the start path (or current working directory) looking for
    a .git directory. The SAWMILL_GIT_ROOT environment variable can be used
    to override detection.

    Args:
        start_path: Directory to start searching from. If None, uses the
            current working directory.

    Returns:
        Path to the git root directory, or None if not in a git repository.
    """
    # Check for environment variable override first
    env_override = os.environ.get("SAWMILL_GIT_ROOT")
    if env_override:
        override_path = Path(env_override)
        if override_path.exists():
            return override_path
        # If override is set but path doesn't exist, return it anyway
        # (for testing purposes, the caller can validate)
        return override_path

    # Determine starting directory
    if start_path is None:
        start_path = Path.cwd()
    else:
        start_path = Path(start_path).resolve()

    # Walk up the directory tree looking for .git
    current = start_path
    while current != current.parent:  # Stop at filesystem root
        if (current / ".git").exists():
            return current
        current = current.parent

    # Check the root directory too
    if (current / ".git").exists():
        return current

    return None
