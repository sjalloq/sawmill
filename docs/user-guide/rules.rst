Rules
=====

A *rule* waives log messages. Waived messages still appear in counts and
reports but never fail ``sawmill check``. Rules live in TOML files under
``.sawmill/rules/`` and are listed by the manifest (see
:doc:`sawmill-directory`). Commit them with the project.

There is one rule format. Which file lists a rule, and which manifest key
lists the file, decides where the rule applies.

A rule file
-----------

.. code-block:: toml

   [rules]
   plugin = "vivado"      # required; the file only applies to this plugin

   [[rule]]               # every Vivado log the file applies to
   id = "Vivado 12-3523"
   comment = "Attempt to change param, harmless. BER-123"

   [[rule]]               # one job only, at most twice per log
   id = "Synth 8-7080"
   regex = "u_dbg_.*"
   logs = ["build/pnr/job_3/vivado.log"]
   max_count = 2
   comment = "Debug core only present in job 3; remove after 2027-01"

   [[rule]]               # by the source file the message refers to
   id = "Synth 8-3331"
   file = "**/ip/snps_pcie/**/*.v"
   comment = "Vendor IP, not ours to fix"

Keys
----

At least one of ``id``, ``regex`` or ``file`` is required. ``comment`` is
always required.

============== ========================= ===================================================
Key            Type                      Meaning
============== ========================= ===================================================
``id``         string                    Exact match on the plugin's message ID.
``regex``      string                    Python regex searched over the message's raw text,
                                         with ``re.DOTALL``. Validated on load.
``file``       glob                      Matched against the path in the message's file
                                         reference.
``logs``       list of globs             Only logs whose path, relative to the project root,
                                         matches. Absent means every log the file applies to.
``severity``   string                    Only messages with this severity id
                                         (case-insensitive).
``max_count``  integer >= 1              Waive at most this many matches; the rest are
                                         unwaived.
``per``        ``"log"`` | ``"target"``  Scope of ``max_count``. Default ``"log"``. Only
                                         valid with ``max_count``.
``comment``    string                    Required, non-empty. Rationale, ticket, expiry.
``author``     string                    Optional. Written by the TUI.
``date``       string                    Optional. Written by the TUI.
``name``       string                    Optional stable label used in output instead of
                                         ``file#n``.
============== ========================= ===================================================

Unknown keys are an error. Errors give the file and line number.

Rules never depend on line numbers.

Globs
^^^^^

- ``**`` matches across directories; ``*`` and ``?`` do not cross ``/``.
- ``logs`` globs are relative to the project root.
- ``file`` is matched against the path as written in the log. If that path
  is relative, it is also resolved from the project root and matched again.

Matching
--------

For each message in a log:

1. Candidate rule files are the manifest's plugin-wide files (``[manifest]
   rules``) whose ``plugin`` equals the target's plugin, then the target's
   own files (``[[target]] rules``).
2. Files are tried in listed order, rules in file order.
3. The first rule whose every present key matches wins.
4. If that rule has ``max_count`` and its count is exhausted, the message is
   unwaived. Later rules are **not** tried.

A rule is *used* when it matched at least one message anywhere in the run.
Unused rules are listed as warnings by ``check`` and ``rules unused``; they
never fail a run. Set ``unused_rules = "ignore"`` on a target to silence
them for that target.

Messages over a ``max_count`` limit are listed under ``Overflows:`` in
``check`` output and in the report's ``overflows`` array.

Scope
-----

======================== ============================== ==================
Listed in                Applies to                     Affects ``check``
======================== ============================== ==================
``[manifest] rules``     every target with that plugin  yes
``[[target]] rules``     that target                    yes
rule ``logs`` key        the matching logs only         yes
TUI session hide (``h``) current session                no
======================== ============================== ==================

A file listed by a target must have the target's ``plugin``; otherwise it is
a configuration error. A plugin-wide file for another plugin is skipped for
that target.

There is no personal rule file. Session hiding in the TUI is the only
filter that is not checked in.

Writing rules
-------------

From the TUI
^^^^^^^^^^^^

Select a message and press ``w``. The waive modal appends one ``[[rule]]``
to a rule file and re-applies rules immediately. See
:doc:`tui-usage`.

By hand
^^^^^^^

Add a ``[[rule]]`` block to a file under ``.sawmill/rules/`` and list the
file in the manifest. Editing and deleting rules is always done in a text
editor.

From a run
^^^^^^^^^^

``sawmill rules generate TARGET`` prints a rule file that waives every
currently unwaived message of the target:

.. code-block:: console

   $ sawmill rules generate pnr --min-level 1 > .sawmill/rules/pnr-baseline.toml

.. code-block:: toml

   # Generated by sawmill rules generate for soc:pnr on 2026-11-07
   # Review every rule and replace the comment before committing.

   [rules]
   plugin = "vivado"

   [[rule]]  # 12 matches, first: Attempt to change param
   id = "Vivado 12-3523"
   comment = "TODO: explain why this is acceptable"
   author = "jane@example.com"
   date = "2026-11-07"

- One ``[[rule]]`` per unique message ID, sorted by severity, then count,
  then ID.
- Messages with no ID or no known severity are skipped.
- ``--min-level N`` keeps severity levels ``>= N`` (default 1).
- ``author`` comes from ``SAWMILL_AUTHOR``, else git ``user.email``, else
  git ``user.name``; it is omitted if none is set.

Replace each ``comment`` before committing, then list the file in the
manifest.

Auditing rules
--------------

.. code-block:: console

   $ sawmill rules list pnr       # rules in scope, in matching order
   $ sawmill rules unused --all   # rules that matched nothing

``rules list`` prints, per target, one line per rule::

   == soc:pnr
   vivado.toml#1  id=Vivado 12-3523  # Attempt to change param, harmless. BER-123
   vivado-pnr.toml#2  id=Synth 8-7080 regex=u_dbg_.* logs=[build/pnr/job_3/vivado.log]  max_count=2/log  # Debug core ...

``rules unused`` prints ``display  path:line  # comment``, or
``No unused rules.``. Both exit 0 unless the configuration is invalid.

Rule references
^^^^^^^^^^^^^^^

Output refers to a rule as ``<file>#<n>`` (1-based position in the file),
or ``<file>:<name>`` when the rule has a ``name``.
