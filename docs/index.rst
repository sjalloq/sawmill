Sawmill
=======

A plugin-driven terminal log analyser.

Sawmill parses structured tool logs through plugins, applies checked-in
rules from a project manifest, and reports what is left. ``sawmill check``
gates CI on the result; ``sawmill view`` opens a terminal UI for triage and
for writing new rules.

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
   user-guide/rules
   user-guide/sawmill-directory

.. toctree::
   :maxdepth: 2
   :caption: Plugin Guide

   plugin-guide/what-is-a-plugin
   plugin-guide/pre-defined-filters
   plugin-guide/writing-a-plugin

.. toctree::
   :maxdepth: 2
   :caption: Performance

   performance/overview
   performance/plugin-api-2
   performance/store-investigation

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
   development/manifest-design
