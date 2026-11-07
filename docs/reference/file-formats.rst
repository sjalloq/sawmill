File Formats
============

All configuration is TOML. Unknown keys are errors, reported with file and
line.

manifest.toml
-------------

Location: ``<project root>/.sawmill/manifest.toml``. Full description in
:doc:`/user-guide/sawmill-directory`.

.. code-block:: toml

   [manifest]
   name = "soc"                              # required
   rules = ["vivado.toml"]                    # plugin-wide rule files
   report = "build/${build}/sawmill-report.json"
   fail_on = "warning"

   [vars]                                     # optional defaults for ${name}
   build = "top"

   [[target]]
   name = "pnr"                               # required
   plugin = "vivado"                          # required
   logs = ["build/${build}/pnr/job_*/vivado.log"]  # required, non-empty
   rules = ["vivado-pnr.toml"]
   fail_on = "critical_warning"
   unused_rules = "warn"                      # warn | ignore

   [target.plugin_options]
   mode = "implementation"

========================= ====== ==================== ====================================
Key                       Type   Default              Notes
========================= ====== ==================== ====================================
``manifest.name``         string (required)           Unique across discovered manifests
``manifest.rules``        list   ``[]``               Files in ``.sawmill/rules/``
``manifest.report``       string none                 Relative to the project root
``manifest.fail_on``      string plugin default       Severity id
``vars.<name>``           string none                 Default for ``${name}``
``target.name``           string (required)           Unique within the manifest
``target.plugin``         string (required)           Installed plugin name
``target.logs``           list   (required)           Globs relative to the project root
``target.rules``          list   ``[]``               Files in ``.sawmill/rules/``
``target.fail_on``        string ``manifest.fail_on`` Severity id
``target.unused_rules``   string ``"warn"``           ``"warn"`` or ``"ignore"``
``target.plugin_options`` table  ``{}``               Passed to the plugin's ``configure``
========================= ====== ==================== ====================================

The plugin default ``fail_on`` is the plugin's second-lowest severity level.

``[vars]`` keys are identifiers (``[A-Za-z_][A-Za-z0-9_]*``). ``${name}`` is
expanded in every ``logs`` entry and in ``report``, not in ``rules``,
``name`` or ``plugin``. ``--var NAME=VALUE`` overrides or supplies a value.
A ``$`` not followed by ``{`` is literal; an unterminated ``${`` is a
manifest error. A reference with no value is an error (exit 2) when the
target runs or the report path is resolved.

Rule files
----------

Location: ``<project root>/.sawmill/rules/*.toml``. Full description in
:doc:`/user-guide/rules`.

.. code-block:: toml

   [rules]
   plugin = "vivado"          # required

   [[rule]]
   name = "dbg-core"          # optional label
   id = "Synth 8-7080"
   regex = "u_dbg_.*"
   file = "**/rtl/dbg/*.sv"
   logs = ["build/top/pnr/job_3/vivado.log"]
   severity = "warning"
   max_count = 2
   per = "log"                # log | target; needs max_count
   comment = "Debug core only in job 3; remove after 2027-01"
   author = "jane@example.com"
   date = "2026-11-07"

================ ================== ==========================================
Key              Type               Notes
================ ================== ==========================================
``rules.plugin`` string             Required
``id``           string             Exact message ID
``regex``        string             Python regex, ``re.search`` with DOTALL on
                                    raw text
``file``         glob               Message file reference
``logs``         list of globs      Relative to the project root
``severity``     string             Severity id, case-insensitive
``max_count``    integer >= 1       Default unlimited
``per``          string             ``"log"`` (default) or ``"target"``
``comment``      string             Required, non-empty
``author``       string             Optional
``date``         string             Optional
``name``         string             Optional
================ ================== ==========================================

Each rule needs at least one of ``id``, ``regex`` or ``file``.

JSON report
-----------

Written by ``sawmill report`` (default format) and ``sawmill check
--report PATH``.

.. code-block:: json

   {
     "generated": "2026-11-07T10:15:00.000000+00:00",
     "sawmill_version": "0.5.0",
     "passed": false,
     "targets": [
       {
         "manifest": "soc",
         "name": "pnr",
         "plugin": "vivado",
         "fail_on": "critical_warning",
         "fail_on_level": 2,
         "vars": {"build": "top"},
         "passed": false,
         "no_logs": false,
         "counts": {"error": 0, "critical_warning": 1, "warning": 7, "info": 120, "other": 0},
         "waived": 5,
         "unwaived": 123,
         "logs": [
           {
             "path": "build/top/pnr/job_3/vivado.log",
             "passed": false,
             "counts": {"error": 0, "critical_warning": 1, "warning": 7, "info": 120, "other": 0},
             "waived": 5,
             "unwaived": 123,
             "failures": [
               {
                 "message_id": "Timing 38-282",
                 "severity": "critical_warning",
                 "line": 4120,
                 "content": "The design failed to meet the timing requirements."
               }
             ],
             "waived_messages": [
               {
                 "message_id": "Synth 8-7080",
                 "severity": "warning",
                 "line": 912,
                 "rule": "vivado-pnr.toml#1"
               }
             ]
           }
         ],
         "rules_used": [
           {
             "file": "/work/soc/.sawmill/rules/vivado-pnr.toml",
             "index": 0,
             "name": null,
             "display": "vivado-pnr.toml#1",
             "id": "Synth 8-7080",
             "regex": "u_dbg_.*",
             "file_glob": null,
             "logs": ["build/top/pnr/job_3/vivado.log"],
             "severity": null,
             "max_count": 2,
             "per": "log",
             "comment": "Debug core only present in job 3",
             "matches": 2
           }
         ],
         "rules_unused": [],
         "overflows": [
           {
             "rule": {"display": "vivado-pnr.toml#1", "...": "rule_ref fields"},
             "scope": "build/top/pnr/job_3/vivado.log",
             "count": 3,
             "max_count": 2
           }
         ]
       }
     ],
     "rules_unused": []
   }

Top level:

=================== ================================================================
Field               Meaning
=================== ================================================================
``generated``       ISO 8601 UTC timestamp
``sawmill_version`` Version that wrote the report
``passed``          True when every target passed
``targets``         One entry per selected target, in run order
``rules_unused``    Rules (``rule_ref``) unused across the whole run, after
                    honouring each target's ``unused_rules``; each rule once
=================== ================================================================

Target:

=================== ================================================================
Field               Meaning
=================== ================================================================
``manifest``        Manifest name
``name``            Target name
``plugin``          Plugin name
``fail_on``         Effective severity id
``fail_on_level``   Its numeric level
``vars``            Resolved manifest variables, name to value; ``{}`` when none
``passed``          No failing log and at least one log
``no_logs``         True when the globs matched nothing
``counts``          Severity id to count, most severe first, then ``other``
``waived``          Waived messages
``unwaived``        Unwaived messages
``logs``            One entry per log
``rules_used``      ``rule_ref`` for each rule that matched in this target
``rules_unused``    ``rule_ref`` for each rule that matched nothing in this
                    target; empty with ``unused_rules = "ignore"``
``overflows``       ``rule`` (``rule_ref``), ``scope`` (log path or target),
                    ``count``, ``max_count``
=================== ================================================================

Log: ``path`` (relative to the project root), ``passed``, ``counts``,
``waived``, ``unwaived``, ``failures`` (``message_id``, ``severity``,
``line``, ``content``) and ``waived_messages`` (``message_id``,
``severity``, ``line``, ``rule`` display name).

``rule_ref``:

============== =================================================================
Field          Meaning
============== =================================================================
``file``       Rule file path
``index``      0-based position in the file
``name``       Rule ``name`` or null
``display``    ``<file>#<n>`` (1-based) or ``<file>:<name>``
``id``         Match keys as written, null when absent
``regex``
``file_glob``  The rule's ``file`` key
``logs``
``severity``
``max_count``  Limit, or null
``per``        ``"log"`` or ``"target"``
``comment``    Rule comment
``matches``    Messages matched in this target
============== =================================================================

JUnit XML
---------

``sawmill report --format junit`` renders the same data:

.. code-block:: xml

   <?xml version='1.0' encoding='UTF-8'?>
   <testsuites name="sawmill" tests="8" failures="1" errors="0" time="0">
     <testsuite name="soc:pnr" timestamp="2026-11-07T10:15:00+00:00" tests="8" failures="1" errors="0">
       <properties>
         <property name="counts.error" value="0" />
         <property name="counts.critical_warning" value="1" />
         <property name="waived" value="5" />
         <property name="unwaived" value="123" />
         <property name="fail_on" value="critical_warning" />
         <property name="vars.build" value="top" />
         <property name="plugin" value="vivado" />
       </properties>
       <testcase classname="soc:pnr" name="build/top/pnr/job_0/vivado.log" />
       <testcase classname="soc:pnr" name="build/top/pnr/job_3/vivado.log">
         <failure message="1 unwaived messages at or above critical_warning" type="failure">critical_warning [Timing 38-282] The design failed to meet the timing requirements.</failure>
       </testcase>
     </testsuite>
   </testsuites>

- One ``<testsuite>`` per target, named ``manifest:target``.
- One ``<testcase>`` per log, named by its path. A failing log has a
  ``<failure>`` with one line per failing message.
- A target with no logs has one failing ``(no logs)`` test case.
- Properties: ``counts.<severity>`` for each severity and ``other``,
  ``waived``, ``unwaived``, ``fail_on``, ``vars.<name>`` for each
  resolved variable, ``plugin``, and ``rules_unused``
  (comma-separated display names) when non-empty.

User config.toml
----------------

Location: ``~/.config/sawmill/config.toml``. Optional. Relative ``roots`` resolve
against the current directory; ``~`` is not expanded. There is no
project-level config file; project settings live in the manifest.

.. code-block:: toml

   [general]
   roots = ["/home/jane/work/fpga", "/proj/asic"]   # manifest search roots

   [output]
   color = true
   format = "text"

========================== ========== ===============================================================================
Key                        Default    Notes
========================== ========== ===============================================================================
``general.roots``          ``[]``     Manifest search roots, used when neither ``--manifest`` nor ``--root`` is given
``general.default_plugin`` none       Parsed but unused; reserved
``output.color``           ``true``   Parsed but unused; reserved
``output.format``          ``"text"`` Parsed but unused; reserved
========================== ========== ===============================================================================
