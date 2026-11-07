CLI Reference
=============

Generated from ``sawmill <command> --help``. Every command accepts
``-h``/``--help``.

Exit status: 0 success; 1 ``check`` found a failing target; 2
configuration, manifest, rule-file, discovery or usage error.

sawmill
-------

.. code-block:: text

   sawmill [OPTIONS] COMMAND [ARGS]...
   sawmill LOGFILE            # shorthand for `sawmill view LOGFILE`

====================== =====================================
Option                 Description
====================== =====================================
``--version``          Show the version and exit.
``--help``, ``-h``     Show this message and exit.
====================== =====================================

sawmill init
------------

.. code-block:: text

   sawmill init [OPTIONS]

Create ``.sawmill/manifest.toml``, or append a target to it.

======================== =========== ===================================================
Option                   Value       Description
======================== =========== ===================================================
``--name``               TEXT        Manifest name (default: current directory name).
``--target``             NAME GLOB   Append a target NAME whose logs match GLOB.
``--plugin``             TEXT        Plugin for ``--target`` (default: auto-detect).
``--help``, ``-h``                   Show this message and exit.
======================== =========== ===================================================

sawmill view
------------

.. code-block:: text

   sawmill view [OPTIONS] [TARGET]

Open TARGET, every target of the manifest, or a LOGFILE in the TUI.

======================== =========== ===================================================
Option                   Value       Description
======================== =========== ===================================================
``--manifest``           PATH        Use exactly this manifest; no directory walk.
``--root``               DIR         Directory to search for manifests (repeatable).
``--plugin``             NAME        Plugin to parse a log file with.
``--fail-on``            SEV         Severity id overriding every target's fail_on.
``--var``                NAME=VALUE  Set a manifest variable (repeatable).
``--help``, ``-h``                   Show this message and exit.
======================== =========== ===================================================

sawmill check
-------------

.. code-block:: text

   sawmill check [OPTIONS] [TARGET...]

Run manifest targets and exit non-zero on unwaived failures.

======================== =========== ===================================================
Option                   Value       Description
======================== =========== ===================================================
``--all``                            Run every target of every manifest.
``--fail-on``            SEV         Severity at or above which unwaived messages fail,
                                     for every target.
``--report``             PATH        Also write the JSON report to PATH.
``--manifest``           PATH        Use exactly this manifest; no directory walk.
``--root``               DIR         Directory to search for manifests (repeatable).
``--var``                NAME=VALUE  Set a manifest variable (repeatable).
``--help``, ``-h``                   Show this message and exit.
======================== =========== ===================================================

sawmill report
--------------

.. code-block:: text

   sawmill report [OPTIONS] [TARGET...]

Report on manifest targets; always exits 0 unless the configuration is
invalid.

======================== ===================== =========================================
Option                   Value                 Description
======================== ===================== =========================================
``--all``                                      Report every target of every manifest.
``--fail-on``            SEV                   Severity at or above which unwaived
                                               messages fail, for every target.
``--format``             [json|text|junit]     Report format. [default: json]
``--output``, ``-o``     PATH                  Write to PATH. With no PATH, use the
                                               manifest's ``report`` setting.
``--manifest``           PATH                  Use exactly this manifest; no directory
                                               walk.
``--root``               DIR                   Directory to search for manifests
                                               (repeatable).
``--var``                NAME=VALUE            Set a manifest variable (repeatable).
``--help``, ``-h``                             Show this message and exit.
======================== ===================== =========================================

sawmill rules
-------------

.. code-block:: text

   sawmill rules [OPTIONS] COMMAND [ARGS]...

List, audit and generate rules. Subcommands: ``generate``, ``list``, ``unused``.

======================== =========== ===================================================
Option                   Value       Description
======================== =========== ===================================================
``--help``, ``-h``                   Show this message and exit.
======================== =========== ===================================================

sawmill rules list
------------------

.. code-block:: text

   sawmill rules list [OPTIONS] [TARGET...]

List the rules in scope for each target, in matching order.

======================== =========== ===================================================
Option                   Value       Description
======================== =========== ===================================================
``--all``                            Select every target of every manifest.
``--manifest``           PATH        Use exactly this manifest; no directory walk.
``--root``               DIR         Directory to search for manifests (repeatable).
``--help``, ``-h``                   Show this message and exit.
======================== =========== ===================================================

sawmill rules unused
--------------------

.. code-block:: text

   sawmill rules unused [OPTIONS] [TARGET...]

Run targets and list rules that matched nothing across the run.

======================== =========== ===================================================
Option                   Value       Description
======================== =========== ===================================================
``--all``                            Run every target of every manifest.
``--manifest``           PATH        Use exactly this manifest; no directory walk.
``--root``               DIR         Directory to search for manifests (repeatable).
``--var``                NAME=VALUE  Set a manifest variable (repeatable).
``--help``, ``-h``                   Show this message and exit.
======================== =========== ===================================================

sawmill rules generate
----------------------

.. code-block:: text

   sawmill rules generate [OPTIONS] TARGET

Run TARGET and print a rule file waiving its unwaived messages.

======================== =========== ===================================================
Option                   Value       Description
======================== =========== ===================================================
``--min-level``          N           Only generate rules for messages at or above
                                     severity level N. [default: 1]
``--manifest``           PATH        Use exactly this manifest; no directory walk.
``--root``               DIR         Directory to search for manifests (repeatable).
``--var``                NAME=VALUE  Set a manifest variable (repeatable).
``--help``, ``-h``                   Show this message and exit.
======================== =========== ===================================================

sawmill plugins
---------------

.. code-block:: text

   sawmill plugins [OPTIONS] COMMAND [ARGS]...

List and inspect installed plugins. Subcommands: ``info``, ``list``.

======================== =========== ===================================================
Option                   Value       Description
======================== =========== ===================================================
``--help``, ``-h``                   Show this message and exit.
======================== =========== ===================================================

sawmill plugins list
--------------------

.. code-block:: text

   sawmill plugins list [OPTIONS]

List installed plugins.

======================== =========== ===================================================
Option                   Value       Description
======================== =========== ===================================================
``--help``, ``-h``                   Show this message and exit.
======================== =========== ===================================================

sawmill plugins info
--------------------

.. code-block:: text

   sawmill plugins info [OPTIONS] NAME

Show hooks, filters, severity levels and grouping fields for plugin NAME.

======================== =========== ===================================================
Option                   Value       Description
======================== =========== ===================================================
``--help``, ``-h``                   Show this message and exit.
======================== =========== ===================================================
