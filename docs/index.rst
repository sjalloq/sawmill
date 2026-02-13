Sawmill
=======

A plugin-driven terminal log analyzer.

Sawmill provides an interactive TUI for browsing, filtering, and triaging
structured tool logs, plus a CLI mode for CI pipeline integration. A plugin
architecture keeps the core tool-agnostic --- plugins teach sawmill how to
parse each tool's output.

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   getting-started/what-is-sawmill
   getting-started/quickstart

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   user-guide/cli-usage
   user-guide/tui-usage
   user-guide/ci-integration
   user-guide/waivers
   user-guide/sawmill-directory

.. toctree::
   :maxdepth: 2
   :caption: Plugin Guide

   plugin-guide/what-is-a-plugin
   plugin-guide/pre-defined-filters
   plugin-guide/writing-a-plugin

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/cli-reference
   reference/file-formats
   reference/api

.. toctree::
   :maxdepth: 2
   :caption: Development

   development/contributing
