CI Integration
==============

Sawmill can gate your CI pipeline on log quality. Use ``--check`` to
exit non-zero when unwaived messages exceed a severity threshold.

Check mode
----------

.. code-block:: console

   $ sawmill build.log --check

In check mode, sawmill:

1. Parses the log file using the auto-detected (or ``--plugin``) plugin.
2. Loads waivers from ``.sawmill/waivers.toml`` (or ``--waivers``).
3. Counts unwaived messages at or above the failure threshold.
4. Exits with code **1** if any are found, **0** otherwise.

Failure threshold
-----------------

``--fail-on`` sets the minimum severity that causes a failure:

.. code-block:: console

   $ sawmill build.log --check --fail-on warning

If ``--fail-on`` is omitted, the default threshold is the **second-lowest
severity level** from the plugin. For a plugin with levels
``note (0) / warning (1) / error (2) / fatal (3)``, the default is
``warning`` (level 1) --- meaning notes pass, but warnings and above fail.

Waivers in CI
-------------

Waived messages are excluded from the failure count:

.. code-block:: console

   $ sawmill build.log --check --waivers .sawmill/waivers.toml

If ``--waivers`` is not specified, sawmill auto-discovers
``.sawmill/waivers.toml`` (or ``sawmill/waivers.toml``) in the current
directory.

See :doc:`/user-guide/waivers` for the waiver file format.

Suppressions do NOT affect CI
------------------------------

Suppressions are display-only. If you combine ``--suppress`` or
``--suppress-id`` with ``--check``, sawmill emits a warning to stderr:

.. code-block:: text

   Warning: --suppress/--suppress-id affects display only, not CI pass/fail.
   Use --waivers for CI acceptance.

Suppressed messages are still counted toward CI pass/fail. Use waivers to
formally accept messages.

JSON reports
------------

``--report`` writes a JSON summary to a file:

.. code-block:: console

   $ sawmill build.log --check --report report.json

The report structure:

.. code-block:: json

   {
     "metadata": {
       "log_file": "build.log",
       "plugin": "vivado",
       "timestamp": "2026-01-15T10:30:00+00:00",
       "fail_on_level": 1
     },
     "exit_code": 0,
     "summary": {
       "total": 100,
       "suppressed": 5,
       "waived": 10,
       "by_severity": {"error": 3, "warning": 20, "note": 77},
       "waived_by_severity": {"error": 1, "warning": 5, "note": 4}
     },
     "issues": [
       {
         "message_id": "Vivado 12-3523",
         "severity": "warning",
         "content": "Attempt to change...",
         "line": 42,
         "raw_text": "WARNING: [Vivado 12-3523] ..."
       }
     ],
     "waived": [
       {
         "message_id": "Synth 8-6157",
         "severity": "warning",
         "content": "...",
         "line": 100,
         "waiver_message_id": "Synth 8-6157",
         "waiver_reason": "Expected in this design"
       }
     ],
     "suppressed": [
       {
         "message_id": "Common 17-55",
         "severity": "note",
         "content": "...",
         "line": 5,
         "raw_text": "INFO: [Common 17-55] ..."
       }
     ],
     "unused_waivers": [
       {
         "message_id": "DRC RTSTAT-10",
         "reason": "No longer triggered"
       }
     ]
   }

Auditing
--------

**Show waived messages** in the output:

.. code-block:: console

   $ sawmill build.log --show-waived

**Report unused waivers** (stale waivers that no longer match any
messages):

.. code-block:: console

   $ sawmill build.log --report-unused

CI pipeline examples
--------------------

GitHub Actions
^^^^^^^^^^^^^^

.. code-block:: yaml

   - name: Check log quality
     run: |
       pip install sawmill sawmill-plugin-vivado
       sawmill build.log --check --fail-on warning --report report.json

   - name: Upload report
     if: always()
     uses: actions/upload-artifact@v4
     with:
       name: sawmill-report
       path: report.json

GitLab CI
^^^^^^^^^

.. code-block:: yaml

   check_logs:
     script:
       - pip install sawmill sawmill-plugin-vivado
       - sawmill build.log --check --fail-on warning --report report.json
     artifacts:
       when: always
       paths:
         - report.json

Makefile
^^^^^^^^

.. code-block:: makefile

   check-logs:
   	sawmill build.log --check --fail-on warning --report report.json
