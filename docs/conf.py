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

autodoc_member_order = "bysource"
autodoc_typehints = "description"

# Render Google-style ``Attributes:`` sections as ``:ivar:`` fields so they
# do not duplicate the attribute entries autodoc already generates.
napoleon_use_ivar = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}
