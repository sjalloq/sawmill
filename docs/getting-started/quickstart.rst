Quickstart
==========

Install
-------

Install sawmill and a plugin for your EDA tool:

.. code-block:: console

   $ pip install sawmill sawmill-plugin-vivado

Verify the installation:

.. code-block:: console

   $ sawmill --version
   sawmill 0.1.0

   $ sawmill --list-plugins
   ┌────────┬─────────┬───────────────────────────────────────┐
   │ Name   │ Version │ Description                           │
   ├────────┼─────────┼───────────────────────────────────────┤
   │ vivado │ 0.1.0   │ Xilinx Vivado log parser for sawmill  │
   └────────┴─────────┴───────────────────────────────────────┘

Browse interactively
--------------------

Open a log file in the TUI:

.. code-block:: console

   $ sawmill build.log

Sawmill auto-detects the plugin (Vivado, Quartus, etc.) and opens an
interactive view:

- **Severity bar** at the top shows message counts per level. Press
  number keys (``1``--``4``) to toggle levels on and off.
- **Search bar** accepts regex patterns, or prefix filters like
  ``sev:error`` or ``id:Synth 8-*``.
- **Message table** shows Line, Severity, ID, and Message columns. Use
  arrow keys, ``j``/``k``, or ``g``/``G`` to navigate.
- **Detail panel** shows the full text of the highlighted message.
- Press ``s`` to suppress a message ID, ``w`` to waive it, ``Ctrl+S``
  to save, and ``q`` to quit.

See :doc:`/user-guide/tui-usage` for the full TUI reference.

Run in CI
---------

Use ``--check`` to gate your pipeline on log quality:

.. code-block:: console

   $ sawmill build.log --check --fail-on warning --report report.json

This command:

1. Parses the log and loads any waivers from ``.sawmill/waivers.toml``.
2. Checks for unwaived messages at ``warning`` level or above.
3. Writes a JSON report to ``report.json``.
4. Exits with code 1 if failures are found, 0 otherwise.

See :doc:`/user-guide/ci-integration` for CI pipeline examples.

The ``.sawmill/`` directory
---------------------------

After your first save (``Ctrl+S`` in the TUI), a ``.sawmill/`` directory
appears in your project root:

.. code-block:: text

   .sawmill/
   ├── config.toml      # Output preferences (optional)
   ├── suppress.toml    # Suppressed message IDs
   └── waivers.toml     # Waiver entries (commit this!)

Commit ``waivers.toml`` and ``config.toml`` to version control.
Consider adding ``suppress.toml`` to ``.gitignore`` since suppressions
are personal display preferences.

See :doc:`/user-guide/sawmill-directory` for details.
