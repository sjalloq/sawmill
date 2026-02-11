The ``.sawmill/`` Directory
===========================

Overview
--------

Sawmill stores project-level configuration in a ``.sawmill/`` directory
in your project root:

.. code-block:: text

   .sawmill/
   ├── config.toml      # General and output settings
   ├── suppress.toml    # Suppressed message IDs and patterns
   └── waivers.toml     # Waiver entries for CI acceptance

This directory is created automatically the first time you save from the
TUI (``Ctrl+S``).

Directory naming
----------------

Sawmill accepts either ``.sawmill/`` or ``sawmill/`` as the
configuration directory. The ``.sawmill/`` form is recommended (hidden
directory, consistent with ``.git/``, ``.github/``, etc.).

If **both** ``.sawmill/`` and ``sawmill/`` exist in the same directory,
sawmill raises an error:

.. code-block:: text

   Ambiguous config: both .sawmill/ and sawmill/ exist in /path/to/project.
   Remove one to resolve.

Configuration --- ``config.toml``
---------------------------------

The configuration file has two sections:

.. code-block:: toml

   [general]
   default_plugin = "vivado"    # Plugin to use when auto-detection is skipped

   [output]
   color = true                 # Enable/disable colour output
   format = "text"              # Default output format: text, json, or count

**User-level configuration** can be placed at
``~/.config/sawmill/config.toml``. Local (project-level) configuration
overrides user-level settings with a **shallow per-section merge** ---
if a local file defines ``[output]``, the entire ``[output]`` section
comes from the local file, not a field-by-field merge.

Suppressions --- ``suppress.toml``
----------------------------------

Suppressions hide messages from the display. They have **no effect on
CI pass/fail**.

.. code-block:: toml

   [suppress]
   message_ids = [
       "Common 17-55",
       "Vivado 12-1023",
   ]
   patterns = [
       "INFO:.*Synthesizing",
   ]

``message_ids`` is a list of exact message IDs to hide. ``patterns`` is
a list of regex patterns --- messages with ``raw_text`` matching any
pattern are hidden.

In the TUI, press ``s`` to suppress a message ID. The ``message_ids``
list is updated when you save (``Ctrl+S``).

Waivers --- ``waivers.toml``
-----------------------------

See :doc:`/user-guide/waivers` for the full waiver format and semantics.

Version control
---------------

Recommended ``.gitignore`` policy:

- **Commit** ``waivers.toml`` --- waivers are team decisions with audit
  trails. They should be reviewed in code review.
- **Commit** ``config.toml`` --- shared project defaults.
- **Consider ignoring** ``suppress.toml`` --- suppressions are personal
  display preferences. Team members may want different suppression lists.

.. code-block:: text

   # .gitignore
   .sawmill/suppress.toml
