"""CLI package for sawmill.

Re-exports the main CLI entry point for compatibility.
"""

from sawmill.cli.commands import cli

__all__ = ["cli"]
