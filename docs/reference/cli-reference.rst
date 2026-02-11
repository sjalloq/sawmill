CLI Reference
=============

Usage: ``sawmill [OPTIONS] [LOGFILE]``

.. list-table::
   :header-rows: 1
   :widths: 25 10 15 50

   * - Flag
     - Type
     - Default
     - Description
   * - ``LOGFILE``
     - path
     -
     - Log file to analyze. Opens TUI unless batch flags are present.
   * - ``--version``
     - flag
     -
     - Show version and exit.
   * - ``--list-plugins``
     - flag
     -
     - List all available plugins and exit.
   * - ``--plugin``
     - string
     -
     - Force a specific plugin (bypasses auto-detection).
   * - ``--show-info``
     - flag
     -
     - Show detailed info about a plugin. Requires ``--plugin``.
   * - ``--list-groupings``
     - flag
     -
     - List available grouping fields from the plugin and exit.
   * - ``--list-severity``
     - flag
     -
     - List available severity levels from the plugin and exit.
   * - ``--severity``
     - string
     -
     - Filter to show only messages at or above this severity level. See :doc:`/user-guide/cli-usage`.
   * - ``--filter``
     - string
     -
     - Regex pattern to include matching messages.
   * - ``--suppress``
     - string
     -
     - Regex pattern to exclude matching messages. Repeatable. See :doc:`/user-guide/cli-usage`.
   * - ``--suppress-id``
     - string
     -
     - Message ID to exclude. Repeatable.
   * - ``--format``
     - choice
     - ``text``
     - Output format: ``text`` (coloured), ``json`` (JSONL), or ``count`` (summary).
   * - ``--id``
     - string
     -
     - Message ID pattern to include (supports wildcards, e.g. ``Synth 8-*``). Repeatable.
   * - ``--category``
     - string
     -
     - Category to include (from plugin pre-defined filters). Repeatable.
   * - ``--generate-waivers``
     - flag
     -
     - Generate waiver TOML from log messages. Output to stdout. See :doc:`/user-guide/waivers`.
   * - ``--waiver-level``
     - int
     - ``1``
     - Minimum severity level for waiver generation.
   * - ``--check``
     - flag
     -
     - Check mode: exit 1 if unwaived messages above threshold. See :doc:`/user-guide/ci-integration`.
   * - ``--fail-on``
     - string
     -
     - With ``--check``, set min failure severity. Default: second-lowest from plugin.
   * - ``--waivers``
     - path
     -
     - Path to waiver TOML file. See :doc:`/user-guide/waivers`.
   * - ``--show-waived``
     - flag
     -
     - Display messages that were waived (with waiver reasons).
   * - ``--report-unused``
     - flag
     -
     - Report waivers that didn't match any messages (stale waivers).
   * - ``--report``
     - path
     -
     - Write JSON summary report to this file. See :doc:`/user-guide/ci-integration`.
   * - ``--summary``
     - flag
     -
     - Show summary counts by severity and message ID.
   * - ``--group-by``
     - choice
     -
     - Group output by field: ``severity``, ``id``, ``file``, or ``category``.
   * - ``--top``
     - int
     - ``5``
     - Limit messages shown per group with ``--group-by``. ``0`` = no limit.
   * - ``--batch``
     - flag
     -
     - Force batch mode (no TUI). Implied by any output/filter/check flag.
   * - ``-h`` / ``--help``
     - flag
     -
     - Show help and exit.

Batch mode detection
--------------------

Sawmill runs in batch mode (no TUI) when **any** of these conditions
are true:

- ``--batch`` is passed.
- Any filter, output, or check flag is present (``--severity``,
  ``--filter``, ``--suppress``, ``--id``, ``--category``,
  ``--format`` explicitly set, ``--check``, ``--fail-on``,
  ``--waivers``, ``--show-waived``, ``--report-unused``, ``--report``,
  ``--summary``, ``--group-by``, ``--generate-waivers``).
- Standard input is not a TTY (piped input, ``CliRunner``, etc.).
