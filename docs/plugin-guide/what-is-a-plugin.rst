What is a Plugin?
=================

Concept
-------

Sawmill's core is tool-agnostic. It knows how to display, filter, and
triage log messages, but it does **not** know how to parse any specific
tool's output. Plugins bridge that gap.

A plugin is a separate Python package that teaches sawmill how to read a
particular tool's log format. Each plugin is installed alongside sawmill
and discovered automatically at runtime.

What a plugin provides
----------------------

A plugin implements one or more hooks from the ``SawmillHookSpec``
interface:

``can_handle(path) -> float``
   Detection --- examine a file and return a confidence score (0.0 to
   1.0) indicating how well this plugin can parse it.

``load_and_parse(path) -> list[Message]``
   Parsing --- open the file, parse every line, group multi-line
   messages, extract severity and message IDs, and return a flat list
   of ``Message`` objects.

``get_severity_levels() -> list[dict]`` (**required**)
   Define the tool's severity levels with ``id``, ``name``, ``level``
   (int), and ``style`` (Rich format string). Levels must be
   consecutive integers starting at 0 (lowest severity).

``get_filters() -> list[dict]``
   Pre-defined filter categories (e.g. ``timing``, ``drc``, ``synth``)
   that users can activate with ``--category``.

``extract_file_reference(content) -> FileRef | None``
   Extract source file and line number references from message content.

``get_grouping_fields() -> list[dict]``
   Declare custom grouping dimensions (beyond the defaults of severity,
   id, file, and category).

Discovery
---------

Plugins are discovered via Python `entry points
<https://packaging.python.org/en/latest/specifications/entry-points/>`_
under the ``sawmill.plugins`` group. A plugin's ``pyproject.toml``
declares itself like this:

.. code-block:: toml

   [project.entry-points."sawmill.plugins"]
   vivado = "sawmill_plugin_vivado:VivadoPlugin"

After installation (``pip install sawmill-plugin-vivado``), sawmill finds
the plugin automatically.

**List installed plugins:**

.. code-block:: console

   $ sawmill --list-plugins

**Show plugin details** (severity levels, filters, hooks):

.. code-block:: console

   $ sawmill --show-info --plugin vivado

Auto-detection
--------------

When you run ``sawmill logfile.log`` without ``--plugin``, sawmill asks
each installed plugin "can you handle this file?" by calling
``can_handle(path)``. The plugin with the highest confidence score
(>= 0.5) is selected.

- If **no plugin** has confidence >= 0.5, sawmill reports an error.
- If **multiple plugins** tie at >= 0.5, sawmill reports a conflict and
  asks you to use ``--plugin`` to disambiguate.
