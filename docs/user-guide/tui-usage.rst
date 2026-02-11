TUI Usage
=========

Launch the TUI by running sawmill with just a filename:

.. code-block:: console

   $ sawmill build.log

Layout
------

The TUI has six panels, top to bottom:

1. **Header** --- App name (``sawmill``) on the left, log filename on the
   right.
2. **Severity bar** --- Total message count and per-severity counts with
   colour coding. Shows number-key hints (``[1]``, ``[2]``, etc.) next to
   each level. Also shows waived/suppressed counts when applicable.
3. **Search bar** --- Text input for filter expressions. Placeholder text
   shows supported prefixes.
4. **Message table** --- Columns: Line, Severity, ID, Message. The Message
   column auto-sizes to fill available width.
5. **Detail panel** --- Full ``raw_text`` of the highlighted message.
6. **Footer** --- Keybinding hints.

Navigating
----------

- **Arrow keys** or **j/k** --- Move cursor up/down in the message table.
- **g** --- Jump to the first message.
- **G** --- Jump to the last message.
- **Tab** --- Toggle focus between the search bar and the message table.

Severity filtering
------------------

Press number keys **1** through **4** to toggle individual severity
levels on and off. The severity bar dims levels that are hidden.

Levels are numbered from lowest to highest severity (``1`` = lowest,
e.g. Note). The mapping depends on the plugin --- use ``--list-severity``
to see the order.

Searching
---------

Press **/** to focus the search bar. The search bar supports three kinds
of filter:

**Plain text** --- treated as a case-insensitive regex matched against
``raw_text``:

.. code-block:: text

   timing.*slack

**Severity prefix** --- ``sev:<id>`` or ``severity:<id>`` shows only
messages with that severity:

.. code-block:: text

   sev:error

**ID prefix** --- ``id:<pattern>`` filters by message ID using fnmatch
wildcards:

.. code-block:: text

   id:Synth 8-*

Multiple prefixes compose with AND logic. Press **Esc** to clear the
filter and return focus to the table.

Sorting
-------

Press **o** to cycle through sort modes:

1. **line** (default) --- by line number in the log file.
2. **severity** --- most severe first.
3. **id** --- alphabetical by message ID.
4. **count** --- most frequent message ID first.

The current sort mode is shown in the Messages panel subtitle.

Suppressing
-----------

Press **s** on a highlighted message to suppress its message ID. All
messages with that ID are hidden from the table.

Press **v** to toggle visibility of suppressed messages. When visible,
suppressed messages appear dimmed.

The severity bar shows "N suppressed" when suppressions are active.

Suppressions are display-only and do not affect CI pass/fail.

Waiving
-------

Press **w** on a highlighted message to open the waive modal. The modal
presents:

- **Message ID** (read-only) --- the ID of the message being waived.
- **Severity** (read-only) --- the message's severity level.
- **Reason** (required) --- free text explaining why this is acceptable.
- **Pattern** --- defaults to the message content. Leave empty to waive
  all instances of this message ID.
- **Content match type** --- radio buttons: ``raw string`` (substring
  match) or ``regex``.
- **Author** --- pre-filled from:

  1. ``SAWMILL_AUTHOR`` environment variable
  2. ``git config user.email``
  3. ``git config user.name``
  4. Empty (you must fill it in)

- **File** (read-only) --- shows the waiver file path for reference.

Press **Enter** to confirm or **Escape** to cancel.

See :doc:`/user-guide/waivers` for the waiver file format and matching
semantics.

Saving
------

Press **Ctrl+S** to save suppressions and waivers to disk.

- Suppressions are written to ``.sawmill/suppress.toml``.
- Waivers are appended to ``.sawmill/waivers.toml`` (or the file
  specified with ``--waivers``).

Press **q** to quit. If there are unsaved changes, a confirmation dialog
appears:

- **Enter** --- save and quit.
- **q** --- quit without saving.
- **Escape** --- cancel (stay in the TUI).

Keybinding reference
--------------------

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Key
     - Action
   * - ``q``
     - Quit (with dirty-state check)
   * - ``/``
     - Focus search bar
   * - ``Esc``
     - Clear filter, return to table
   * - ``Tab``
     - Toggle focus between search and table
   * - ``1``--``4``
     - Toggle severity level visibility
   * - ``o``
     - Cycle sort mode
   * - ``s``
     - Suppress/un-suppress by message ID
   * - ``v``
     - Toggle suppressed message visibility
   * - ``w``
     - Waive highlighted message
   * - ``Ctrl+S``
     - Save
   * - ``j`` / ``k``
     - Move cursor down / up
   * - ``g`` / ``G``
     - Jump to top / bottom

.. note::

   The footer shows ``?`` for Help, but this binding is **not yet
   implemented**.
