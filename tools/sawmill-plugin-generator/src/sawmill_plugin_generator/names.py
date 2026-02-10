"""Name validation and derivation for plugin generation."""

from __future__ import annotations

import re

import click


def validate_name(name: str) -> None:
    """Validate a plugin name.

    Args:
        name: The plugin name to validate.

    Raises:
        click.BadParameter: If the name is invalid.
    """
    if not name:
        raise click.BadParameter("Plugin name cannot be empty.")

    if name != name.lower():
        raise click.BadParameter(f"Plugin name must be lowercase: '{name}'. Use '{name.lower()}'.")

    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        if name[0].isdigit():
            raise click.BadParameter(f"Plugin name must start with a letter: '{name}'.")
        raise click.BadParameter(
            f"Plugin name can only contain lowercase letters, digits, and hyphens: '{name}'."
        )

    if name == "sawmill":
        raise click.BadParameter("Plugin name cannot be 'sawmill'.")


def derive_names(name: str) -> dict[str, str]:
    """Derive all identifier forms from a plugin name.

    Args:
        name: A validated plugin name (e.g. "quartus" or "quartus-prime").

    Returns:
        Dict with keys: plugin_name, package_name, module_name,
        class_name, entry_point_key, directory_name.
    """
    # "quartus-prime" → "quartus_prime"
    underscored = name.replace("-", "_")

    # "quartus-prime" → "QuartusPrime"
    title = "".join(part.capitalize() for part in name.split("-"))

    return {
        "plugin_name": name,
        "package_name": f"sawmill-plugin-{name}",
        "module_name": f"sawmill_plugin_{underscored}",
        "class_name": f"{title}Plugin",
        "entry_point_key": name,
        "directory_name": f"sawmill-plugin-{name}",
    }
