The manifest
============

All project configuration lives in a ``.sawmill/`` directory: a manifest
that names the project and its targets, and the rule files the targets use.
The directory containing ``.sawmill/`` is the *project root*.

Layout
------

.. code-block:: text

   soc/                         project root
   ├── .sawmill/
   │   ├── manifest.toml
   │   └── rules/
   │       ├── vivado.toml
   │       ├── vivado-pnr.toml
   │       └── slang.toml
   └── build/
       ├── lint/top.log  sub_a.log  sub_b.log
       └── pnr/job_0/vivado.log ... job_7/vivado.log

Commit the whole ``.sawmill/`` directory.

- Log globs are relative to the project root.
- Rule file names are relative to ``.sawmill/rules/``.

manifest.toml
-------------

.. code-block:: toml

   [manifest]
   name = "soc"
   rules = ["vivado.toml", "slang.toml"]   # plugin-wide rule files
   report = "build/sawmill-report.json"       # default for `report --output`
   fail_on = "warning"                        # default for all targets

   [[target]]
   name = "lint"
   plugin = "slang"
   logs = ["build/lint/*.log"]

   [[target]]
   name = "pnr"
   plugin = "vivado"
   logs = ["build/pnr/job_*/vivado.log"]
   rules = ["vivado-pnr.toml"]
   fail_on = "critical_warning"
   unused_rules = "warn"                      # warn (default) | ignore

   [target.plugin_options]
   mode = "implementation"

``[manifest]``
^^^^^^^^^^^^^^

=========== ======== ======== ===========================================================
Key         Type     Required Meaning
=========== ======== ======== ===========================================================
``name``    string   yes      Unique across all discovered manifests.
``rules``   list     no       Plugin-wide rule files. Each applies to every target whose
                              plugin matches the file's ``[rules] plugin``.
``report``  string   no       Report path relative to the project root. Used by
                              ``sawmill report --output`` with no path.
``fail_on`` string   no       Default failure severity id for every target.
=========== ======== ======== ===========================================================

``[[target]]``
^^^^^^^^^^^^^^

================== ======== ======== ====================================================
Key                Type     Required Meaning
================== ======== ======== ====================================================
``name``           string   yes      Unique within the manifest.
``plugin``         string   yes      Plugin that parses the logs.
``logs``           list     yes      Non-empty list of globs relative to the project
                                     root. Absolute paths are rejected.
``rules``          list     no       Rule files for this target only. Each must have
                                     the target's plugin.
``fail_on``        string   no       Overrides ``[manifest] fail_on``.
``unused_rules``   string   no       ``"warn"`` (default) or ``"ignore"``.
``plugin_options`` table    no       Passed to the plugin's ``configure`` hook before
                                     parsing.
================== ======== ======== ====================================================

Unknown keys are an error, reported with the file and line.

``fail_on`` resolution, first match wins: the ``--fail-on`` option, the
target's ``fail_on``, the manifest's ``fail_on``, then the plugin's
second-lowest severity level. An id the plugin does not define is a
configuration error.

A target whose globs match no file fails ``check`` and shows as empty in
``view``.

.. _build-variables:

Build variables
^^^^^^^^^^^^^^^

Some flows choose the build directory per make target, for example
``run.<target>``. A static ``logs`` glob cannot name it, and one manifest
target per make target duplicates the target list. Instead, declare
variables in an optional ``[vars]`` table and reference them as
``${name}``:

.. code-block:: toml

   [manifest]
   name = "fpga"
   report = "run.${build}/sawmill-report.json"

   [vars]
   build = "top"                              # default value

   [[target]]
   name = "pnr"
   plugin = "vivado"
   logs = ["run.${build}/pnr/job_*/vivado.log"]

.. code-block:: console

   $ sawmill check                    # uses run.top/
   $ sawmill check --var build=sub    # uses run.sub/

- Keys are identifiers; values are strings. ``[vars]`` only provides
  defaults; ``--var NAME=VALUE`` (repeatable) overrides or supplies a value
  and need not match a ``[vars]`` key. Values no manifest references are
  ignored.
- ``${name}`` expands in every ``logs`` entry and in ``report`` only, not in
  ``rules``, ``name`` or ``plugin``. A ``$`` not followed by ``{`` is
  literal; an unterminated ``${`` is a manifest error.
- ``--var`` is accepted by ``check``, ``report``, ``rules unused``,
  ``rules generate`` and ``view``.
- A variable with no value is an error (exit 2) naming the target and the
  variable. It is only checked when a target runs or the report path is
  resolved, so ``rules list`` needs no value and has no ``--var`` option.
- The resolved values are recorded in the ``check`` header (for example
  ``[build=sub]``), the JSON report and JUnit properties; see
  :doc:`/reference/file-formats`.

Plugin options
^^^^^^^^^^^^^^

``[target.plugin_options]`` is passed unchanged to the plugin's
``configure`` hook, once per target, before any log is parsed. What the
keys mean is up to the plugin; see its documentation. If the plugin rejects
them, sawmill exits with status 2. If the plugin has no ``configure`` hook,
sawmill prints a warning on stderr and ignores them.

Creating a manifest
-------------------

.. code-block:: console

   $ cd soc
   $ sawmill init --name soc
   created /work/soc/.sawmill/manifest.toml

``sawmill init`` writes ``.sawmill/manifest.toml`` with every key present
and commented out, and creates ``.sawmill/rules/``. ``--name`` defaults to
the current directory name. It refuses to overwrite an existing manifest.

Add targets with ``--target NAME GLOB``:

.. code-block:: console

   $ sawmill init --target pnr 'build/pnr/job_*/vivado.log'
   appended target 'pnr' (plugin vivado) to /work/soc/.sawmill/manifest.toml
   created /work/soc/.sawmill/rules/pnr.toml

- Creates the manifest first if it does not exist.
- Detects the plugin from the first file matching the glob, unless
  ``--plugin`` is given. With no matching file, ``--plugin`` is required.
- Lists ``pnr.toml`` as the target's rule file and creates it with the
  ``[rules]`` header if missing. An existing rule file is left alone.
- Preserves existing comments and formatting in the manifest.
- Quote the glob so the shell does not expand it.

Discovery
---------

Commands that take targets find manifests by walking *down* from one or
more roots. Roots, highest precedence first:

1. ``--manifest PATH``: exactly this manifest, no walk. ``PATH`` must be a
   ``.sawmill/manifest.toml``. Cannot be combined with ``--root``.
2. ``--root DIR``, repeatable.
3. ``[general] roots`` in ``~/.config/sawmill/config.toml``.
4. The current directory.

The walk:

- skips hidden directories other than ``.sawmill``, and ``.git``;
- does not enter directories that git would ignore: it applies
  ``.git/info/exclude`` and every ``.gitignore`` from the top of the
  enclosing repository down, with git's rules for nesting, negation and
  anchoring. Keep build output ignored and the walk stays fast on large
  trees. Global excludes (``core.excludesFile``) are not read;
- does not follow symbolic links;
- loads a manifest reached from overlapping roots once;
- fails if two manifests have the same ``name``.

Addressing targets
^^^^^^^^^^^^^^^^^^

- ``manifest:target`` always works.
- ``target`` alone works when exactly one discovered manifest has that
  target; otherwise it is ambiguous and an error.
- With no target and no ``--all``, ``check``, ``report``, ``view`` and
  ``rules`` use every target of the single discovered manifest. If more
  than one manifest was found this is an error; pass ``--all`` or name the
  targets.
- ``--all`` selects every target of every manifest and cannot be combined
  with target names. ``view`` has no ``--all``.

.. code-block:: console

   $ sawmill check                       # all targets of the one manifest
   $ sawmill check pnr                   # unique bare name
   $ sawmill check soc:pnr fpga:synth   # qualified names
   $ sawmill check --all --root ~/work   # every manifest under ~/work

Discovery, manifest and rule-file errors exit with status 2.
