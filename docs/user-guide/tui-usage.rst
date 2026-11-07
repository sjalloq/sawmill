TUI Usage
=========

.. code-block:: console

   $ sawmill view              # every target of the discovered manifest
   $ sawmill view pnr          # one target
   $ sawmill build/top.log     # one log, no manifest needed

Layout
------

Top to bottom:

1. **Header**: ``sawmill``, then one tab per view: ``Overview`` (manifest
   mode only) and one tab per target.
2. **Severity bar**: total and per-severity counts for the active target,
   with the ``1``--``4`` key hints, plus waived and hidden counts.
3. **Search bar**: filter expression for the active target.
4. **Messages**: the overview table or the active target's message table.
5. **Detail panel**: full raw text of the highlighted message.
6. **Footer**: key hints. Press ``?`` for the full list.

Switch tabs with ``←`` and ``→``.

Overview tab
------------

Shown when the TUI is opened from a manifest. One row per target, and one
row per log beneath it:

====================== ================================================
Column                 Content
====================== ================================================
Target / Log           Target name, then each log path
Counts                 Counts per severity
Waived                 Messages waived by rules
Hidden                 Messages hidden this session
Result                 ``PASS`` or ``FAIL`` against ``fail_on``
====================== ================================================

Press ``Enter`` on a target row to open its tab; on a log row to open the
target's tab filtered to that log (``log:<path>`` in the search bar).

Target tabs
-----------

One tab per target. The table merges messages from every log of the target:

============ ================================================================
Column       Content
============ ================================================================
St           Status: ``W`` waived, ``H`` hidden, blank otherwise
Line         Line number in the log
Log          Log path relative to the project root
Severity     Severity id
ID           Message ID
Message      Message text; fills the remaining width
============ ================================================================

By default only unwaived, unhidden messages are shown. Press ``v`` to show
waived and hidden rows as well, marked in the ``St`` column.

Press ``o`` to cycle the sort order: line, severity, ID, count.

Navigation: arrow keys or ``j``/``k``; ``g``/``Home`` top, ``G``/``End``
bottom; ``Tab`` toggles focus between the search bar and the table.

Severity levels
^^^^^^^^^^^^^^^

``1`` to ``4`` toggle severity levels on and off, ``1`` being the lowest.
The severity bar dims hidden levels. ``sawmill plugins info NAME`` lists a
plugin's levels.

Searching
---------

Press ``/`` to focus the search bar. Terms combine with AND.

======================= ======================================================
Term                    Meaning
======================= ======================================================
``sev:<id>``            Severity id (also ``severity:<id>``)
``id:<pattern>``        Message ID, fnmatch wildcards: ``id:Synth 8-*``
``cat:<name>``          Category (also ``category:<name>``)
``log:<pattern>``       Log path, fnmatch, case-sensitive:
                        ``log:build/pnr/job_3/*``
anything else           Case-insensitive regex over the raw text
======================= ======================================================

Quote terms containing spaces. ``Esc`` clears the filter and returns to
the table.

.. code-block:: text

   sev:warning log:build/pnr/job_3/* timing.*slack

Waiving
-------

Press ``w`` on a message to open the waive modal. It builds one rule:

============== ==============================================================
Field          Meaning
============== ==============================================================
Message        The selected message (read-only)
Scope          ``this log`` (adds ``logs = [<log>]``), ``this target`` or
               ``all targets using this plugin``
Match          ``id only``, ``id + substring`` (stored as an escaped
               ``regex``) or ``id + regex``; the pattern is prefilled and
               editable
Max count      Optional ``max_count``, with ``per`` log or target
Comment        Required
Destination    Rule file to append to. Plugin scope offers the manifest's
               plugin-wide files for the plugin; log and target scope offer
               the target's files. The last file is preselected.
Author         Prefilled from ``SAWMILL_AUTHOR`` or git config; editable
Date           Today (read-only)
============== ==============================================================

``Enter`` confirms, ``Esc`` cancels.

On confirm the rule is appended to the destination file as a ``[[rule]]``
block using ``tomlkit``, so existing content and comments are untouched.
Rules are then re-applied to the loaded messages without re-parsing the
logs, and the counts update.

If the target lists no rule file, the TUI asks you to add one to the
manifest. The TUI only adds rules; edit or delete them in a text editor and
press ``r``.

Hiding
------

Press ``h`` to hide every message with the selected ID for this session;
press it again on a hidden row (with ``v``) to unhide. Hiding is never
saved and does not affect ``check``. Hidden counts appear in the overview.

Refreshing
----------

- ``r`` re-reads the manifest and rule files and re-applies them. Logs are
  not re-parsed.
- ``R`` also re-reads the logs.

The cursor position is kept.

No manifest
-----------

``sawmill view LOGFILE`` (or ``sawmill LOGFILE``) opens the log as a single
target tab with no overview. Rules in ``.sawmill/rules/<plugin>.toml`` beside
the log apply if that file exists.

The first ``w`` of a session, when no rules file exists yet, asks for:

- a rules file name under ``.sawmill/rules/`` beside the log, defaulting to
  ``<plugin>.toml``;
- whether to also create ``.sawmill/manifest.toml`` with this log as a
  target, or create the rules file only.

Later rules in the session go to the same file.

Keys
----

=========== ==============================================
Key         Action
=========== ==============================================
``q``       Quit
``/``       Search / filter messages
``Esc``     Clear filter
``Tab``     Toggle focus
``1``-``4`` Toggle severity levels
``o``       Cycle sort mode
``←`` ``→`` Switch tab
``Enter``   Open target or log (overview)
``v``       Show or hide waived and hidden rows
``w``       Waive: append a rule
``h``       Hide or unhide message ID for the session
``r``       Re-read manifest and rules
``R``       Re-read logs too
``F12``     Screenshot (SVG)
``?``       Help
=========== ==============================================
