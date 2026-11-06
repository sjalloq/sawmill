Manifest and rules redesign
===========================

Status: draft for review, 2026-11-06. Nothing here is implemented yet.

This note replaces the waiver and suppression design described in
``user-guide/waivers.rst`` and ``user-guide/sawmill-directory.rst``. There is
no backwards compatibility requirement; the project is pre-release.

Motivation
----------

The current design grew out of single-block lint flows: one log, one plugin,
one waiver file found in the current directory. It does not fit multi-stage
flows such as the HAPS ProtoCompiler flow, which produces several Synplify
``.srr`` logs and eight parallel Vivado jobs per run. Specific problems:

- one log per invocation, so CI needs shell loops and exit-code merging;
- waivers and suppressions are discovered relative to the current working
  directory, which is arbitrary in CI;
- a waiver has no scope, so a waiver written for one job applies to all;
- waivers and suppressions are two file formats and two matchers with nearly
  identical semantics;
- no way to say "this message is expected at most N times";
- no channel for passing flow mode or other options to a plugin.

Decisions
---------

Taken in discussion on 2026-11-06.

- One rule format. There is no separate suppression file and no
  ``action`` key. A rule is a waiver; which file lists it decides where it
  applies.
- No personal or per-user rule file. Everything that affects what a user
  sees is checked in, so there is no "works for me" drift. Session-only
  hiding in the TUI is the only non-persistent filter.
- All configuration lives under a ``.sawmill/`` directory: the manifest at
  ``.sawmill/manifest.toml`` and rule files under ``.sawmill/rules/``.
- Discovery walks *down* from one or more roots looking for ``.sawmill``
  directories, as FuseSoC does for core files. Each manifest has a unique
  ``name``.
- Subcommands replace the flat flag set: ``check``, ``view``, ``report``,
  ``rules``, ``init``. ``sawmill <logfile>`` remains a shortcut for
  ``view`` without a manifest.
- Unused rules produce a warning, never a failure.
- Rules never depend on line numbers.
- The TUI adds rules; editing and deleting is done in a text editor. A
  refresh key re-reads the manifest and rule files.

Layout
------

::

    haps/
      .sawmill/
        manifest.toml
        rules/
          vivado.toml
          vivado-pnr.toml
          synplify.toml
      build/
        synth/top.srr  sub_a.srr  sub_b.srr
        pnr/job_0/vivado.log ... job_7/vivado.log

The directory containing ``.sawmill/`` is the *project root*. Log globs are
relative to the project root. Rule file names are relative to
``.sawmill/rules/``.

Manifest
--------

.. code-block:: toml

    [manifest]
    name = "haps"
    rules = ["vivado.toml", "synplify.toml"]   # plugin-wide, see rule header
    report = "build/sawmill-report.json"       # default for `report`
    fail_on = "warning"                        # default for all targets

    [[target]]
    name = "synth"
    plugin = "synplify"
    logs = ["build/synth/*.srr"]

    [[target]]
    name = "pnr"
    plugin = "vivado"
    logs = ["build/pnr/job_*/vivado.log"]
    rules = ["vivado-pnr.toml"]
    fail_on = "critical_warning"
    unused_rules = "warn"                      # warn (default) | ignore

    [target.plugin_options]
    mode = "implementation"

Keys:

``[manifest]``
  ``name`` (required, unique across discovered manifests), ``rules``,
  ``report``, ``fail_on``.

``[[target]]``
  ``name`` (required, unique within the manifest), ``plugin`` (required),
  ``logs`` (required, list of globs), ``rules``, ``fail_on``,
  ``unused_rules``, ``plugin_options`` (table passed to the plugin's
  ``configure`` hook).

A target with no matching logs is an error in ``check`` and shown as empty
in ``view``.

Rule files
----------

.. code-block:: toml

    [rules]
    plugin = "vivado"      # required; the file only applies to this plugin

    [[rule]]               # every Vivado log in every target
    id = "Vivado 12-3523"
    comment = "Attempt to change param, harmless. BER-123"

    [[rule]]               # one job only
    id = "Synth 8-7080"
    regex = "u_dbg_.*"
    logs = ["build/pnr/job_3/vivado.log"]
    max_count = 2
    comment = "Debug core only present in job 3; remove after 2027-01"

    [[rule]]               # by referenced source file, as in the Slang lint waivers
    id = "Synth 8-3331"
    file = "**/ip/snps_pcie/**/*.v"
    comment = "Vendor IP, not ours to fix"

Match keys, all optional but at least one of ``id``, ``regex`` or ``file``
is required:

``id``
  Exact match on the plugin's message ID.
``regex``
  Python regex searched over the message's raw text, ``DOTALL``.
``file``
  Glob matched against the path in the message's file reference. ``**``
  is supported. Matched against the path as written in the log and, if that
  is relative, also against it resolved from the project root.
``logs``
  List of globs relative to the project root. The rule applies only to logs
  whose resolved path matches. Absent means every log the file applies to.
``severity``
  Restrict to one severity id. Mostly useful with ``regex``.

Limits and metadata:

``max_count``
  Maximum matches per log (default) before the rule stops waiving and the
  excess counts as unwaived. ``per = "target"`` counts across the target.
``comment``
  Required free text. Tickets, expiry and rationale go here.
``author``, ``date``
  Written by the TUI when it adds a rule. Optional when hand-written.
``name``
  Optional stable identifier so reports and ``rules`` output can refer to
  the rule by something other than file and index.

Matching: for each message, rules from the plugin-wide files are tried
first, then the target's files, in file order and then rule order. The
first rule whose every present key matches wins. A rule counts as used when
it matches at least one message in the run.

Scope hierarchy
---------------

======================== ============================== ==================
Listed in                Applies to                     Used by ``check``
======================== ============================== ==================
``[manifest] rules``     every target with that plugin  yes
``[[target]] rules``     that target                    yes
rule ``logs`` key        the matching logs only         yes
TUI session hide         current session                no
======================== ============================== ==================

Discovery
---------

``sawmill`` looks for manifests by walking down from each root. Roots are,
in order of precedence: ``--manifest PATH`` (no walk, exactly one manifest),
``--root DIR`` (repeatable), ``roots`` in ``~/.config/sawmill/config.toml``,
the current directory. Hidden directories other than ``.sawmill`` and
directories named ``.git`` are skipped. Targets are addressed as
``manifest:target``, or ``target`` alone when unique across all discovered
manifests. Duplicate manifest names are an error.

CLI
---

::

    sawmill check [TARGET...] [--all] [--fail-on SEV] [--report PATH]
    sawmill view  [TARGET | LOGFILE] [--plugin NAME]
    sawmill report [TARGET...] [--format json|text|junit]
    sawmill rules list [TARGET...]
    sawmill rules unused [TARGET...]
    sawmill rules generate TARGET [--min-level N]
    sawmill init [--name NAME]
    sawmill init --target NAME GLOB [--plugin NAME]
    sawmill LOGFILE            # alias for `view LOGFILE`

``check`` exits 1 when any selected target has an unwaived message at or
above its ``fail_on`` level, or when a target has no matching logs. Unused
rules and ``max_count`` overflows are listed in the output. With no target
and no ``--all``, ``check`` runs every target of the single discovered
manifest and errors if more than one manifest was found.

``init`` with no arguments writes ``.sawmill/manifest.toml`` with every key
present and commented, and creates ``.sawmill/rules/``. With ``--target``
it appends a target, detects the plugin from the first log matching the
glob unless ``--plugin`` is given, and scaffolds ``rules/<name>.toml`` with
the ``[rules]`` header.

Plugin API additions
--------------------

``configure(options: dict) -> None``
  Optional hook, called once per target before any log is parsed, with the
  target's ``plugin_options`` table. Plugins without the hook ignore options
  and ``check`` warns if options were given.

No other plugin changes. The log column and per-log counts in the TUI are a
base-app concern.

TUI
---

Opened with ``sawmill view TARGET`` or ``sawmill view`` for all targets of
the discovered manifest.

Overview tab
  One row per target, with one row per log beneath it: counts per severity,
  waived, hidden, pass or fail against ``fail_on``. Enter opens the
  target's tab filtered to that log.

Target tabs
  One tab per target. The table is merged across the target's logs with a
  log column, and group-by message ID shows per-log counts. Filtering by
  log is a filter on the log column, not a separate mode.

Waive modal
  Opened on a message or a message-ID group. Fields: scope (this log, this
  target, all targets using this plugin), match (id only, id plus substring,
  id plus regex, prefilled from the message and editable), ``max_count``
  and per log or per target, comment, destination file. The destination
  defaults from the scope: plugin-wide scope offers the manifest's files
  for that plugin, target scope the target's files, and the last file in the
  list is preselected. Author and date are filled in. Saving appends one
  ``[[rule]]`` block to the file using ``tomlkit`` so existing content and
  comments are untouched, then re-applies rules so counts update live.

Keys
  ``h`` hides the selected message ID for the session. ``R`` re-reads the
  manifest and rule files and re-applies them, keeping the cursor.
  ``shift+R`` also re-reads the logs.

No manifest
  ``sawmill view LOGFILE`` is a single target tab with no overview. The
  waive modal prompts once per session for a rules file path, defaulting
  to ``.sawmill/rules/<plugin>.toml`` beside the log, and offers to run
  ``init`` to create the manifest.

Report
------

``report`` and ``check --report`` write one JSON document covering every
selected target: per target and per log, counts per severity, waived,
unwaived, rules used, rules unused, ``max_count`` overflows, and the pass or
fail result. A JUnit XML format is a thin view over the same data, one test
case per log, for CI systems that render it.

Open questions
--------------

- Whether ``file`` should also accept a plugin-provided label (Vivado run
  name, Synplify project) as an alternative to path globs. Deferred until
  globs prove insufficient.
- Whether ``expires`` deserves enforcement as a first-class key. Deferred;
  today it is a convention in ``comment``.
- Whether the overview should be a tab or a separate screen. Try tabs first.

Implementation plan
-------------------

Each task is independently testable and small enough for one subagent on a
worktree. Order matters within a stage; stages are sequential.

Stage A, data model and loading

A1
  ``Rule`` and ``RuleFile`` models plus a loader with validation and line
  numbers in errors. Replaces ``models/waiver.py``, ``core/waiver.py``
  loader and ``core/suppress.py``.
A2
  ``Manifest`` and ``Target`` models plus loader. Relative path resolution
  for logs and rules. Glob expansion.
A3
  Discovery: walk roots for ``.sawmill/manifest.toml``, address targets by
  ``manifest:target``, detect duplicates.
A4
  ``RuleMatcher``: ordering, all match keys, ``logs`` scoping,
  ``max_count`` per log and per target, used and unused tracking.

Stage B, CLI

B1
  Subcommand skeleton with ``click.Group``; ``sawmill LOGFILE`` alias.
  Move existing options under ``view``. Remove the flat flags.
B2
  ``check``: run targets, apply rules, exit code, text output including
  unused rules and overflows.
B3
  ``report``: JSON then JUnit.
B4
  ``rules list``, ``rules unused``, ``rules generate``.
B5
  ``init`` both forms.
B6
  ``configure`` hook in the hookspec and base plugin; wire
  ``plugin_options`` through ``check`` and ``view``.

Stage C, TUI

C1
  Multi-log model: a target loads N logs, messages carry their source log,
  aggregation groups by ID with per-log counts.
C2
  Target tab with log column and log filter.
C3
  Overview tab.
C4
  Waive modal rewrite: scope, match, count, comment, destination; append
  with ``tomlkit``.
C5
  ``R`` and ``shift+R`` refresh; ``h`` session hide.
C6
  No-manifest path: prompt for rules file, offer ``init``.

Stage D, docs

D1
  Rewrite ``user-guide/waivers.rst``, ``sawmill-directory.rst``,
  ``ci-integration.rst``, ``reference/cli-reference.rst`` and
  ``reference/file-formats.rst``. Remove the stale workflow table from
  ``CLAUDE.md``.
