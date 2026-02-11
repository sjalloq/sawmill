Pre-defined Filters
===================

What are pre-defined filters?
-----------------------------

Plugins can ship **pre-defined filters** --- named regex patterns that
match common categories of messages. For example, a Vivado plugin might
define filters for ``timing``, ``drc``, and ``synth`` message categories.

Each filter has:

- **id** --- unique identifier (used with ``--category``).
- **name** --- human-readable display name.
- **pattern** --- a regular expression.
- **description** --- what the filter matches.

Listing filters
---------------

Use ``--show-info`` to see what filters a plugin provides:

.. code-block:: console

   $ sawmill --show-info --plugin vivado

The output includes a table of all filters with their IDs, names, and
descriptions.

Using filters
-------------

Activate a pre-defined filter with ``--category``:

.. code-block:: console

   $ sawmill build.log --category timing
   $ sawmill build.log --category drc --category synth

Multiple ``--category`` flags can be combined. Messages matching **any**
of the selected categories are included.

Pre-defined filters compose with other filters:

.. code-block:: console

   $ sawmill build.log --category timing --severity warning

This shows only ``warning``-level (and above) messages that match the
``timing`` category.

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

A user can then run:

.. code-block:: console

   $ sawmill build.log --category timing

to see only messages whose content matches ``\[Timing \d+-\d+\]``.
