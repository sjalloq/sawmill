Writing a Plugin
================

This guide walks through creating a sawmill plugin from scratch using
the plugin generator.

Prerequisites
-------------

- Python 3.10+
- sawmill installed (``pip install sawmill``)

Generate a scaffold
-------------------

The plugin generator is a local tool in the sawmill repository. Install
it first:

.. code-block:: console

   $ cd tools/sawmill-plugin-generator
   $ pip install -e .

Then generate a plugin project:

.. code-block:: console

   $ sawmill-new-plugin --name quartus

This creates a ``sawmill-plugin-quartus/`` directory with:

.. code-block:: text

   sawmill-plugin-quartus/
   ├── pyproject.toml               # Package metadata and entry point
   ├── README.md
   ├── Makefile                     # install / test / lint shortcuts
   ├── src/
   │   └── sawmill_plugin_quartus/
   │       ├── __init__.py          # Plugin class export
   │       ├── plugin.py            # Hook implementations (fill in TODOs)
   │       └── patterns.py          # Regex patterns for log parsing
   ├── tests/
   │   ├── conftest.py              # Shared fixtures
   │   ├── test_detection.py        # can_handle() tests
   │   ├── test_parsing.py          # load_and_parse() tests
   │   ├── test_severity.py         # Severity level contract tests
   │   └── test_plugin_contract.py  # Hook interface compliance
   └── examples/
       └── sample.log               # Example log file for development

The hookspec contract
---------------------

Plugins inherit from ``SawmillPlugin`` and decorate methods with
``@hookimpl``:

.. code-block:: python

   from sawmill.plugin import SawmillPlugin, hookimpl

   class QuartusPlugin(SawmillPlugin):
       name = "quartus"
       version = "0.1.0"
       description = "Sawmill plugin for Intel Quartus logs"

Six hooks are available. One is required; the rest are optional.

``can_handle(path) -> float`` (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Return a confidence score from 0.0 to 1.0. Examine the filename,
extension, or first few lines of the file:

.. code-block:: python

   @hookimpl
   def can_handle(self, path):
       if path.suffix == ".log" and "quartus" in path.stem.lower():
           return 0.9
       # Read first lines for tool signature
       try:
           with open(path) as f:
               header = f.read(1024)
           if "Quartus Prime" in header:
               return 0.8
       except OSError:
           pass
       return 0.0

``load_and_parse(path) -> list[Message]`` (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Open the file, parse every line, group multi-line messages, and return
a flat list of ``Message`` objects:

.. code-block:: python

   from sawmill.models.message import Message, FileRef

   @hookimpl
   def load_and_parse(self, path):
       messages = []
       with open(path, errors="replace") as f:
           for line_num, line in enumerate(f, start=1):
               severity, msg_id, content = self._parse_line(line)
               if severity:
                   messages.append(Message(
                       start_line=line_num,
                       end_line=line_num,
                       raw_text=line.rstrip(),
                       content=content,
                       severity=severity,
                       message_id=msg_id,
                   ))
       return messages

``get_severity_levels() -> list[dict]`` (**required**)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Define the tool's severity levels. Levels **must** be consecutive
integers starting at 0 (lowest severity):

.. code-block:: python

   @hookimpl
   def get_severity_levels(self):
       return [
           {"id": "error",   "name": "Error",   "level": 2, "style": "red bold"},
           {"id": "warning", "name": "Warning", "level": 1, "style": "yellow"},
           {"id": "info",    "name": "Info",     "level": 0, "style": "cyan"},
       ]

``get_filters() -> list[dict]`` (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Provide pre-defined filter categories:

.. code-block:: python

   from sawmill.models.filter_def import FilterDefinition

   @hookimpl
   def get_filters(self):
       return [
           FilterDefinition(
               id="timing",
               name="Timing",
               pattern=r"Timing Analyzer",
               source="plugin:quartus",
               description="Timing analysis messages",
           ),
       ]

``extract_file_reference(content) -> FileRef | None`` (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Extract source file references from message content:

.. code-block:: python

   import re
   from sawmill.models.message import FileRef

   @hookimpl
   def extract_file_reference(self, content):
       m = re.search(r'File: (.+?) Line: (\d+)', content)
       if m:
           return FileRef(path=m.group(1), line=int(m.group(2)))
       return None

``get_grouping_fields() -> list[dict]`` (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Declare custom grouping dimensions. The base class provides defaults
(severity, id, file, category). Override to add tool-specific fields:

.. code-block:: python

   @hookimpl
   def get_grouping_fields(self):
       return [
           {"id": "severity", "name": "Severity", "field_type": "builtin",
            "description": "Group by message severity level"},
           {"id": "id", "name": "Message ID", "field_type": "builtin",
            "description": "Group by tool-specific message ID"},
           {"id": "file", "name": "Source File", "field_type": "file_ref",
            "description": "Group by source file path"},
           {"id": "entity", "name": "Design Entity", "field_type": "metadata",
            "description": "Group by design entity name"},
       ]

Metadata fields use ``Message.metadata[field_id]`` --- populate this
dict in ``load_and_parse()``.

The Message model
-----------------

Each ``Message`` has these fields:

``start_line`` / ``end_line``
   Line numbers in the source log (1-indexed). For multi-line messages,
   ``end_line > start_line``.

``raw_text``
   The complete original text (all lines concatenated).

``content``
   Cleaned/extracted message content (without severity prefix, etc.).

``severity``
   Severity level ID (lowercase string matching one of your
   ``get_severity_levels()`` IDs).

``message_id``
   Tool-specific ID (e.g. ``"Synth 8-6157"``). Used for waiver
   matching, suppression, and grouping.

``category``
   Optional category for grouping (e.g. ``"timing"``).

``file_ref``
   Optional ``FileRef(path, line)`` extracted from the message.

``metadata``
   ``dict[str, str]`` for plugin-specific data used by custom grouping
   fields.

Filling in hooks
-----------------

The typical workflow is:

1. Study your tool's log format. Identify the severity prefix pattern,
   message ID format, and multi-line grouping rules.
2. Write regex patterns in ``patterns.py``.
3. Implement ``can_handle()`` to detect the tool's log files.
4. Implement ``load_and_parse()`` to parse lines into messages.
5. Implement ``get_severity_levels()`` with the correct level mapping.
6. Optionally add ``get_filters()`` for common categories.

Testing
-------

The generated scaffold includes test files with fixtures and basic
structure. Run tests with:

.. code-block:: console

   $ make test

The ``test_plugin_contract.py`` file tests that your plugin conforms to
the hookspec interface (severity levels are consecutive ints from 0,
required hooks are implemented, etc.).

Installing
----------

Install the plugin in development mode:

.. code-block:: console

   $ make install    # runs: pip install -e .

Verify it appears in sawmill:

.. code-block:: console

   $ sawmill --list-plugins
   $ sawmill --show-info --plugin quartus

Entry point registration
^^^^^^^^^^^^^^^^^^^^^^^^

The generated ``pyproject.toml`` includes the entry point declaration:

.. code-block:: toml

   [project.entry-points."sawmill.plugins"]
   quartus = "sawmill_plugin_quartus:QuartusPlugin"

This is how sawmill discovers the plugin at runtime. After changing
entry points, reinstall the package (``pip install -e .``).
