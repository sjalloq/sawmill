What is Sawmill?
================

Sawmill is a terminal-based log analysis tool for working with structured
tool logs. It provides two modes of operation:

**Interactive log browser** --- Launch ``sawmill build.log`` to open a TUI
where you can scroll, filter, suppress, and waive messages from tools like
Vivado, Quartus, or any tool with a sawmill plugin.

**CI quality gate** --- Add ``--check`` to run sawmill in batch mode. It
exits non-zero when unwaived messages exceed a severity threshold, making it
easy to embed in CI pipelines.

Key Concepts
------------

Plugin architecture
^^^^^^^^^^^^^^^^^^^

Sawmill's core is tool-agnostic. It does not know how to parse any log
format on its own. Instead, **plugins** teach sawmill how to read a
specific tool's output. Each plugin is a separate Python package that
you install alongside sawmill:

.. code-block:: console

   $ pip install sawmill sawmill-plugin-vivado

Plugins define everything tool-specific: severity levels, message IDs,
multi-line grouping rules, and pre-defined filter categories.

Suppress vs. waive
^^^^^^^^^^^^^^^^^^

Sawmill draws a hard line between two concepts:

**Suppressions** are display preferences. When you suppress a message ID
in the TUI, it is hidden from view. Suppressions are stored in
``.sawmill/suppress.toml`` and have **no effect on CI pass/fail**. Think
of them as "hide this noise."

**Waivers** are auditable team decisions. A waiver records *who* accepted
a message, *when*, and *why*. Waivers are stored in
``.sawmill/waivers.toml``, require ``reason``, ``author``, and ``date``
fields, and **do affect CI** --- waived messages are excluded from the
failure count in ``--check`` mode. Think of them as "reviewed and
accepted."

Dual mode
^^^^^^^^^

Running sawmill with just a filename opens the TUI:

.. code-block:: console

   $ sawmill build.log

Adding any flag (``--severity``, ``--check``, ``--format``, etc.) switches
to batch mode automatically. You can also force batch mode with ``--batch``:

.. code-block:: console

   $ sawmill build.log --batch --severity warning
