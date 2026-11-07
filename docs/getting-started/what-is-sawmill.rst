What is Sawmill?
================

Sawmill is a terminal log analyser for structured tool logs. Plugins parse
each tool's format; sawmill applies the project's rules and reports what is
left.

**CI quality gate**: ``sawmill check`` runs every target in the project
manifest and exits 1 when an unwaived message reaches the target's
``fail_on`` severity.

**Interactive triage**: ``sawmill view`` opens a terminal UI over the same
targets, where you browse, search, hide and waive messages.

Key concepts
------------

Plugins
^^^^^^^

Sawmill's core never parses log content. Each plugin is a separate Python
package that defines a tool's severity levels, message IDs, multi-line
grouping and pre-defined filters:

.. code-block:: console

   $ uv tool install sawmill-parser sawmill-plugin-vivado

Rules and the manifest
^^^^^^^^^^^^^^^^^^^^^^

A project keeps its configuration in ``.sawmill/``:

- ``manifest.toml`` names the project and its *targets*. A target is a
  plugin plus a set of log globs, for example the eight Vivado jobs of a
  place-and-route stage.
- ``rules/*.toml`` hold *rules*. A rule waives matching messages and
  records why. Which manifest key lists a rule file decides whether its
  rules apply to one target or to every target using the plugin.

Rules are checked in. There is no personal rule file, so everyone, and CI,
sees the same result.

Hiding a message ID in the TUI (``h``) lasts for the session only. It is
the one filter that is not checked in and it never affects ``check``.

See :doc:`/user-guide/sawmill-directory` and :doc:`/user-guide/rules`.

Commands
^^^^^^^^

.. code-block:: console

   $ sawmill init                 # create .sawmill/manifest.toml
   $ sawmill check                # CI gate
   $ sawmill view                 # TUI over all targets
   $ sawmill build.log            # TUI over one log, no manifest needed
