from importlib.metadata import version as _version

project = "Sawmill"
copyright = "2026, Sawmill Contributors"
author = "Sawmill Contributors"

release = _version("sawmill-parser")

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_static_path = ["_static"]

autodoc_member_order = "bysource"
autodoc_typehints = "description"

# Suppress duplicate object warnings from Pydantic model fields
# and dataclass fields that appear as both class-level and instance-level
suppress_warnings = ["autodoc.duplicate_object"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
