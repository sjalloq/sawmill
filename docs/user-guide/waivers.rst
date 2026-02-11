Waivers
=======

What is a waiver?
-----------------

A **waiver** is a formal, auditable acceptance of a specific log message.
Unlike :doc:`suppressions </user-guide/sawmill-directory>` (which hide
noise from the display), waivers carry metadata --- who accepted it, when,
and why --- and **affect CI pass/fail**: waived messages are excluded from
the failure count in ``--check`` mode.

File format
-----------

Waivers are stored in TOML files using ``[[waiver]]`` array-of-tables
syntax:

.. code-block:: toml

   [metadata]
   tool = "vivado"  # Optional, for documentation

   [[waiver]]
   message_id = "Vivado 12-3523"
   reason = "Expected warning in this design, reviewed by team"
   author = "engineer@company.com"
   date = "2026-01-15"

   [[waiver]]
   message_id = "Synth 8-6157"
   content_match = "raw"
   content_pattern = "synthesizing module 'top'"
   reason = "Top-level synthesis message, always present"
   author = "engineer@company.com"
   date = "2026-01-15"

   [[waiver]]
   message_id = "DRC RTSTAT-10"
   content_match = "regex"
   content_pattern = "Net .* has no driver"
   reason = "Test stub nets, not connected in final build"
   author = "engineer@company.com"
   date = "2026-01-15"

Fields:

``message_id`` (required)
   The message ID to match. Must match exactly.

``reason`` (required)
   Explanation of why this message is acceptable.

``author`` (required)
   Who created or approved this waiver.

``date`` (required)
   When the waiver was created (ISO format, e.g. ``2026-01-15``).

``content_match`` (optional)
   How to interpret ``content_pattern``. Either ``"raw"`` (substring
   match, the default) or ``"regex"`` (regular expression search).

``content_pattern`` (optional)
   Narrows the match beyond ``message_id``. If omitted, the waiver
   matches **all** instances of the given message ID.

Matching semantics
------------------

Waiver matching is two-stage:

1. **message_id** must match exactly (case-sensitive).
2. If ``content_pattern`` is set, it is applied as a second filter:

   - ``content_match = "raw"`` --- substring match against ``raw_text``.
   - ``content_match = "regex"`` --- regex search against ``raw_text``
     (with ``DOTALL`` flag).

3. If no ``content_pattern`` is set, the waiver matches **all**
   instances of that message ID (catch-all).

When multiple waivers match a message, more specific waivers (those with
a ``content_pattern``) are checked first.

Creating waivers
----------------

There are three ways to create waivers:

**TUI** --- Press ``w`` on a highlighted message. The waive modal
pre-fills the message ID and content. Fill in a reason and confirm.
See :doc:`/user-guide/tui-usage`.

**Generator** --- Use ``--generate-waivers`` to generate a waiver file
from all errors/warnings in a log:

.. code-block:: console

   $ sawmill build.log --generate-waivers > .sawmill/waivers.toml

Review the generated file and update the placeholder ``<reason>`` and
``<author>`` values before committing.

**Hand-edit** --- Create or edit ``.sawmill/waivers.toml`` directly
using the format described above.

Auto-discovery
--------------

When ``--waivers`` is not specified, sawmill looks for a waiver file at:

1. ``.sawmill/waivers.toml`` in the current directory.
2. ``sawmill/waivers.toml`` in the current directory.

If both directories exist, sawmill raises an error (see
:doc:`/user-guide/sawmill-directory`).

To use a different path:

.. code-block:: console

   $ sawmill build.log --check --waivers path/to/waivers.toml

Author discovery
----------------

The TUI's waive modal and the waiver generator both use author
auto-discovery. The author is resolved in this order:

1. ``SAWMILL_AUTHOR`` environment variable.
2. ``git config user.email``.
3. ``git config user.name``.
4. Empty string (you must fill it in manually).

Set ``SAWMILL_AUTHOR`` in your CI environment to ensure waivers have
consistent authorship:

.. code-block:: bash

   export SAWMILL_AUTHOR="ci-bot@company.com"
