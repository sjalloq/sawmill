Plugin API 2
============

``SAWMILL_PLUGIN_API`` is ``"2"``. The change is to ``load_and_parse``,
which now streams messages.

The contract
------------

.. code-block:: python

   @hookspec
   def load_and_parse(self, path: Path) -> Iterator[Message]: ...

- Plugins should be generators reading the file line by line.
- Yield each ``Message`` as soon as it is complete.
- The ``SawmillPlugin`` base class default is a generator that yields
  nothing.
- ``[tool.sawmill] plugin_api`` in a plugin's ``pyproject.toml`` is
  informational; nothing enforces it.

Migrating from API 1
--------------------

API 1 returned ``list[Message]``. To migrate:

- Replace ``messages.append(msg)`` with ``yield msg``.
- Drop the final ``return messages``.
- Flush any in-flight multi-line message after the loop with a final
  ``yield``.

The ``load_messages`` shim
--------------------------

The base app calls plugins through ``sawmill.core.plugin.load_messages``:

.. code-block:: python

   def load_messages(plugin, path) -> Iterator[Message]:
       return iter(plugin.load_and_parse(path))

A legacy list is wrapped with ``iter()``, so API 1 plugins keep working
unchanged. They do not get the memory benefit.

Eager-open pattern
------------------

A plain generator does not run until the first ``next()``, so a missing
file would raise deep inside the consumer. Open the file in an outer
function and return an inner generator over the handle:

.. code-block:: python

   @hookimpl
   def load_and_parse(self, path):
       f = open(path, errors="replace")   # raises here if missing
       return self._iter_messages(f)

   def _iter_messages(self, f):
       try:
           current = None
           for line_num, line in enumerate(f, start=1):
               ...  # build or extend current; yield when complete
           if current is not None:
               yield current             # flush the in-flight message
       finally:
           f.close()

Caveat: a generator that is never iterated keeps its file handle open
until garbage collection.

Allocation guidance
-------------------

Parse time is dominated by Python object creation, not regex or I/O.

- Read with ``for line in f``, never ``readlines()``.
- Use one combined regex per line rather than two tried in sequence.
- Use ``m.groups()`` or a ``NamedTuple``, not a dict per line.
- Intern repeated strings (tool, rule / message ID, file path) through a
  small cache dict.
- Share one ``metadata`` dict per constant value, or omit ``metadata``.

Measured effect on an Xcelium plugin at 200k messages, output identical:

- memory: 820 → 520 B per message
- parse: 0.67 → 0.63 s

The remaining per-message cost is mostly the ``Message`` object itself.
The realistic Python ceiling is about 2 µs and 400 B per message.

Generated plugins
-----------------

The plugin generator template ``plugin.py.j2`` (under
``tools/sawmill-plugin-generator/``) emits a generator-shaped
``load_and_parse``.
