CLI Usage
=========

Sawmill is a set of subcommands. Every option is listed in
:doc:`/reference/cli-reference`.

.. code-block:: text

   sawmill init      create a manifest or add a target
   sawmill view      open targets or a log file in the TUI
   sawmill check     run targets, exit 1 on unwaived failures
   sawmill report    write a JSON, JUnit or text report
   sawmill rules     list, audit and generate rules
   sawmill plugins   list and inspect installed plugins
   sawmill LOGFILE   shorthand for `sawmill view LOGFILE`

Commands that take targets share ``--manifest PATH`` and ``--root DIR``;
see :ref:`discovery <discovery-section>` below. Configuration errors exit
with status 2.

init
----

.. code-block:: console

   $ sawmill init                              # .sawmill/manifest.toml + rules/
   $ sawmill init --name soc                  # set the manifest name
   $ sawmill init --target synth 'build/lint/*.log'
   $ sawmill init --target pnr 'build/pnr/job_*/vivado.log' --plugin vivado

Run from the project root. ``--target`` appends a ``[[target]]``, creating
the manifest if needed, auto-detects the plugin unless ``--plugin`` is
given, and creates ``.sawmill/rules/<name>.toml``. See
:doc:`sawmill-directory`.

view
----

.. code-block:: console

   $ sawmill view                    # every target of the manifest
   $ sawmill view pnr                # one target
   $ sawmill view build/top.log      # one log file, no manifest needed
   $ sawmill build/top.log           # same
   $ sawmill view build/top.log --plugin vivado --fail-on error

- If the argument is an existing file it is opened as a single log, with the
  plugin auto-detected unless ``--plugin`` is given. Rules from
  ``.sawmill/rules/<plugin>.toml`` beside the log apply if that file exists.
- Otherwise the argument is a target name.
- ``--fail-on`` overrides every target's ``fail_on`` for the PASS/FAIL
  display.

See :doc:`tui-usage`.

check
-----

.. code-block:: console

   $ sawmill check                          # all targets of the manifest
   $ sawmill check synth pnr                # selected targets
   $ sawmill check --all                    # every target of every manifest
   $ sawmill check --fail-on error          # override fail_on everywhere
   $ sawmill check --report build/r.json    # also write the JSON report

Exits 0 when every selected target passes, 1 otherwise. Output format and
CI examples are in :doc:`ci-integration`.

report
------

.. code-block:: console

   $ sawmill report                          # JSON on stdout
   $ sawmill report --format junit -o build/sawmill.xml
   $ sawmill report --format text
   $ sawmill report -o                       # write to [manifest] report

Same selection options as ``check``. Always exits 0 unless the
configuration is invalid. Formats are described in
:doc:`/reference/file-formats`.

rules
-----

.. code-block:: console

   $ sawmill rules list                  # rules in scope per target, in matching order
   $ sawmill rules unused --all          # rules that matched nothing in the run
   $ sawmill rules generate pnr > .sawmill/rules/pnr-baseline.toml
   $ sawmill rules generate pnr --min-level 2

- ``list`` reads rule files only; it does not parse logs.
- ``unused`` runs the targets and lists rules that matched nothing.
- ``generate`` runs exactly one target and prints a rule file waiving its
  unwaived messages at or above severity level ``--min-level``.

All exit 0 unless the configuration is invalid. See :doc:`rules`.

plugins
-------

.. code-block:: console

   $ sawmill plugins list
   $ sawmill plugins info vivado

``list`` shows name, version and description of each installed plugin.
``info`` shows the hooks a plugin implements, its filters, severity levels
and grouping fields.

Version
-------

.. code-block:: console

   $ sawmill --version

.. _discovery-section:

Selecting manifests and targets
-------------------------------

- ``--manifest PATH`` uses one ``.sawmill/manifest.toml`` with no search.
- ``--root DIR`` (repeatable) searches below each directory.
- Without either, the roots come from ``[general] roots`` in
  ``~/.config/sawmill/config.toml``, else the current directory.
- Name targets as ``manifest:target``, or ``target`` when unique.

Details: :doc:`sawmill-directory`.
