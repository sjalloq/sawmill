CI Integration
==============

``sawmill check`` runs manifest targets, applies their rules and exits
non-zero when any unwaived message reaches a target's ``fail_on`` level.
It needs a manifest; see :doc:`sawmill-directory`.

Exit codes
----------

=========================== ====== ======== ========
Outcome                     check  report   rules
=========================== ====== ======== ========
All targets pass            0      0        0
A target fails              1      0        0
Configuration error         2      2        2
=========================== ====== ======== ========

*Configuration error* covers invalid manifests, rule files or user config,
discovery errors (no manifest, duplicate names, unknown or ambiguous
targets), unknown ``fail_on`` ids, missing plugins, plugins rejecting their
``plugin_options``, and usage errors.

A target fails when:

- any log has an unwaived message at or above ``fail_on``, or
- its ``logs`` globs match no file.

Unused rules and ``max_count`` overflows are reported but never fail a run.

check output
------------

.. code-block:: console

   $ sawmill check
   == soc:lint (slang, fail_on=warning)
   build/lint/top.log  error=0 warning=0 note=14  waived=3  PASS
   build/lint/sub_a.log  error=0 warning=2 note=9  waived=0  FAIL
       sub_a.sv:12:8: warning: unused variable 'dbg_q' [-Wunused-variable]
       sub_a.sv:40:2: warning: implicit conversion truncates from 5 to 4 bits [-Wwidth-trunc]
   == soc:pnr (vivado, fail_on=critical_warning)
   no logs matched: build/pnr/job_*/vivado.log  FAIL
   Overflows:
       vivado-pnr.toml#2  build/pnr/job_3/vivado.log  3/2
   Unused rules:
       vivado.toml#4  Old timing waiver, BER-99
   check: 0/2 targets passed, 1 unused rules

- One ``== manifest:target (plugin, fail_on=id)`` header per target. When
  the manifest has build variables, the resolved values follow, for example
  ``== fpga:pnr (vivado, fail_on=warning) [build=sub]``.
- One line per log: path relative to the project root, counts per
  severity most severe first (``other=`` only when non-zero), waived count,
  ``PASS`` or ``FAIL``.
- Failing messages are listed under the log, first line of each, up to 20
  per log, then ``... and N more``.
- ``Overflows:`` lists ``rule  scope  count/max_count`` for each exhausted
  ``max_count``.
- ``Unused rules:`` lists rules that matched nothing in the whole run,
  except for targets with ``unused_rules = "ignore"``.
- The last line is the summary.

Warnings, such as ``plugin_options`` given to a plugin without a
``configure`` hook, go to stderr as ``warning: ...``.

Options:

.. code-block:: console

   $ sawmill check pnr --fail-on error          # override fail_on for every target
   $ sawmill check --report build/report.json   # also write the JSON report
   $ sawmill check --all --root /work/fpga      # every manifest under a root

Reports
-------

``sawmill report`` runs the same targets and writes a report without
gating: it exits 0 whatever the result.

.. code-block:: console

   $ sawmill report                          # JSON to stdout
   $ sawmill report --format junit -o build/sawmill.xml
   $ sawmill report --format text            # same text as check
   $ sawmill report -o                       # JSON to the manifest's `report` path

``--output``/``-o`` with no path uses ``[manifest] report``, resolved from
the project root; it is an error if the key is absent. Parent directories
are created.

``check --report PATH`` writes the same JSON document as
``report --format json``.

Each target in the JSON report has a ``vars`` object holding its resolved
build variables, for example ``"vars": {"build": "sub"}``; JUnit records
them as ``vars.<name>`` properties.

The JSON schema and JUnit mapping are in :doc:`/reference/file-formats`.

JUnit
^^^^^

One ``<testsuite>`` per target (named ``manifest:target``), one
``<testcase>`` per log. A failing log has a ``<failure>`` listing its
failing messages. A target with no logs gets a single failing
``(no logs)`` test case. Counts, waived, unwaived, ``fail_on``, plugin and
unused rules are suite ``<property>`` elements.

Examples
--------

GitHub Actions
^^^^^^^^^^^^^^

.. code-block:: yaml

   name: Log check
   on: [push, pull_request]

   jobs:
     sawmill:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: astral-sh/setup-uv@v5
         - run: uv tool install sawmill-parser sawmill-plugin-vivado
         - run: make build    # produces the logs
         - run: sawmill check --report build/sawmill-report.json
         - if: always()
           run: sawmill report --format junit -o build/sawmill.xml
         - if: always()
           uses: actions/upload-artifact@v4
           with:
             name: sawmill-report
             path: build/sawmill-*

GitLab CI
^^^^^^^^^

.. code-block:: yaml

   sawmill:
     stage: test
     script:
       - uv tool install sawmill-parser sawmill-plugin-vivado
       - sawmill check --report build/sawmill-report.json
     after_script:
       - sawmill report --format junit -o build/sawmill.xml
     artifacts:
       when: always
       paths:
         - build/sawmill-report.json
       reports:
         junit: build/sawmill.xml

Makefile
^^^^^^^^

.. code-block:: make

   .PHONY: check-logs
   check-logs: build
   	sawmill check --report build/sawmill-report.json

When the build directory depends on the make target (for example
``run.$(TARGET)``), pass it through as a manifest variable; see
:ref:`build-variables`:

.. code-block:: make

   check-logs: build
   	sawmill check --var build=$(TARGET)

Multiple projects
^^^^^^^^^^^^^^^^^

One invocation covers every target, so no shell loops or exit-code merging
are needed:

.. code-block:: console

   $ sawmill check --all --root fpga --root asic --report build/all.json

Baselining an existing flow
---------------------------

To adopt sawmill on a flow that already has many warnings:

.. code-block:: console

   $ sawmill rules generate pnr > .sawmill/rules/pnr-baseline.toml
   $ $EDITOR .sawmill/rules/pnr-baseline.toml   # replace each TODO comment

Then add ``"pnr-baseline.toml"`` to the target's ``rules`` list. See
:doc:`rules`.
