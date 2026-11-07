Pre-defined Filters
===================

What are pre-defined filters?
-----------------------------

Plugins can ship **pre-defined filters** --- named regex patterns that
match common categories of messages. For example, a Vivado plugin might
define filters for ``timing``, ``drc``, and ``synth`` message categories.

Each filter has:

- **id** --- unique identifier.
- **name** --- human-readable display name.
- **pattern** --- a regular expression.
- **description** --- what the filter matches.

Listing filters
---------------

Use ``sawmill plugins info`` to see what filters a plugin provides:

.. code-block:: console

   $ sawmill plugins info vivado

The output includes a table of all filters with their IDs, names, and
descriptions.

Using filters
-------------

No CLI option applies pre-defined filters. In the TUI search bar
(:doc:`/user-guide/tui-usage`), use the filter's pattern as a regex term,
or ``cat:`` when the plugin sets the message's ``category``. Terms combine
with AND, and ``sev:`` selects a single severity:

.. code-block:: text

   cat:timing sev:warning
   '\[Timing \d+-\d+\]' sev:warning

Single-quote regex terms that contain backslashes or spaces. Both show only ``warning`` messages in the timing group.

Worked example
--------------

Suppose a plugin defines these filters:

.. code-block:: python

   @hookimpl
   def get_filters(self):
       return [
           FilterDefinition(
               id="timing",
               name="Timing",
               pattern=r"\[Timing \d+-\d+\]",
               source="plugin:example",
               description="Timing analysis messages",
           ),
           FilterDefinition(
               id="drc",
               name="Design Rule Checks",
               pattern=r"\[DRC ",
               source="plugin:example",
               description="Design rule check messages",
           ),
       ]

A user can then type this in the TUI search bar:

.. code-block:: text

   '\[Timing \d+-\d+\]'

to see only messages whose text matches the ``timing`` pattern.
