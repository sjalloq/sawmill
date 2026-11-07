Quickstart
==========

Install
-------

Install sawmill and a plugin for your tool:

.. code-block:: console

   $ uv tool install sawmill-parser sawmill-plugin-vivado

Check the installation:

.. code-block:: console

   $ sawmill --version
   $ sawmill plugins list

Look at one log
---------------

.. code-block:: console

   $ sawmill build/synth/vivado.log

The plugin is auto-detected. Use ``/`` to search, ``1``--``4`` to toggle
severity levels, ``?`` for all keys and ``q`` to quit. See
:doc:`/user-guide/tui-usage`.

Create a manifest
-----------------

From the project root:

.. code-block:: console

   $ sawmill init --name myproj
   created /work/myproj/.sawmill/manifest.toml

   $ sawmill init --target synth 'build/synth/*.log'
   appended target 'synth' (plugin vivado) to /work/myproj/.sawmill/manifest.toml
   created /work/myproj/.sawmill/rules/synth.toml

.. code-block:: toml

   # .sawmill/manifest.toml (comments trimmed)
   [manifest]
   name = "myproj"

   [[target]]
   name = "synth"
   plugin = "vivado"
   logs = ["build/synth/*.log"]
   rules = ["synth.toml"]

Commit ``.sawmill/``. See :doc:`/user-guide/sawmill-directory`.

Triage
------

.. code-block:: console

   $ sawmill view

The Overview tab shows each target and log with counts and PASS/FAIL.
Press ``Enter`` on a log to open it, select a message and press ``w`` to
add a rule to ``.sawmill/rules/synth.toml``. Counts update immediately.
See :doc:`/user-guide/rules`.

Gate CI
-------

.. code-block:: console

   $ sawmill check --report build/sawmill-report.json
   == myproj:synth (vivado, fail_on=warning)
   build/synth/vivado.log  error=0 critical_warning=0 warning=0 info=212  waived=4  PASS
   check: 1/1 targets passed

``check`` exits 0 when every target passes, 1 when any fails and 2 on a
configuration error. See :doc:`/user-guide/ci-integration`.
