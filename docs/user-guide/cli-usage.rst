CLI Usage
=========

Basic usage
-----------

Run sawmill with a log file:

.. code-block:: console

   $ sawmill build.log

With no extra flags, sawmill opens the TUI. Add ``--batch`` (or any
output/filter/check flag) to run in batch mode:

.. code-block:: console

   $ sawmill build.log --batch

Sawmill auto-detects the appropriate plugin by asking each installed
plugin how confident it is about the file. To override auto-detection:

.. code-block:: console

   $ sawmill build.log --plugin vivado

List installed plugins:

.. code-block:: console

   $ sawmill --list-plugins

Show detailed information about a plugin, including its filters and
severity levels:

.. code-block:: console

   $ sawmill --show-info --plugin vivado

Output formats
--------------

Sawmill supports three output formats:

``--format text`` (default)
   Coloured, human-readable output. Each message is printed with its
   severity style applied.

``--format json``
   JSONL (one JSON object per line). Each object contains ``start_line``,
   ``end_line``, ``raw_text``, ``content``, ``severity``, ``message_id``,
   ``category``, and optionally ``file_ref``.

``--format count``
   A single-line summary: ``total=N error=N warning=N ...``

Example:

.. code-block:: console

   $ sawmill build.log --format json | jq '.severity'

Filtering
---------

**By severity** --- show messages at or above a severity level:

.. code-block:: console

   $ sawmill build.log --severity warning

The valid severity names come from the plugin. Use
``--list-severity --plugin <name>`` to see them.

**By regex** --- include only messages matching a pattern:

.. code-block:: console

   $ sawmill build.log --filter "timing.*slack"

**By message ID** --- include messages with matching IDs. Supports
glob-style wildcards:

.. code-block:: console

   $ sawmill build.log --id "Synth 8-*"
   $ sawmill build.log --id "Vivado 12-3523" --id "DRC *"

**By category** --- include messages in a given category (defined by the
plugin's pre-defined filters):

.. code-block:: console

   $ sawmill build.log --category timing --category drc

Suppressing display noise
--------------------------

Suppressions hide messages from output. They have **no effect on CI
pass/fail** (see :doc:`/user-guide/ci-integration`).

**By regex pattern:**

.. code-block:: console

   $ sawmill build.log --suppress "INFO:.*Synthesizing"

**By message ID:**

.. code-block:: console

   $ sawmill build.log --suppress-id "Vivado 12-1023"

Both options can be repeated. If ``--suppress`` or ``--suppress-id`` is
combined with ``--check``, sawmill emits a stderr warning reminding you
that suppressions are display-only.

Grouping and summary
--------------------

**Summary mode** shows counts by severity and message ID, similar to
``hal_log_parser.py``:

.. code-block:: console

   $ sawmill build.log --summary

**Group-by mode** groups messages by a field and shows sample messages
per group:

.. code-block:: console

   $ sawmill build.log --group-by severity
   $ sawmill build.log --group-by id --top 3
   $ sawmill build.log --group-by file
   $ sawmill build.log --group-by category

``--top N`` limits the number of sample messages shown per group
(default: 5, ``--top 0`` for no limit).

List available grouping fields (including plugin-specific ones):

.. code-block:: console

   $ sawmill --list-groupings --plugin vivado

Waiver generation
-----------------

Generate a waiver TOML file from errors and warnings in a log:

.. code-block:: console

   $ sawmill build.log --generate-waivers > waivers.toml

By default, messages at severity level 1 and above are included. Adjust
the threshold with ``--waiver-level``:

.. code-block:: console

   $ sawmill build.log --generate-waivers --waiver-level 0

The generated file contains placeholder values for ``reason`` and
``author`` that you should review and update before committing.

See :doc:`/user-guide/waivers` for the waiver file format.
