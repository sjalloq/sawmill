Performance overview
====================

This page records what was measured, what was changed, and the current
numbers.

What was measured
-----------------

Measurements were taken on 2026-11-04 with a synthetic Xcelium log from
``tools/bench/gen_xcelium_log.py`` (200k messages, 24 MB).

.. list-table:: Before
   :header-rows: 1

   * - Step
     - Before
   * - Plugin parse alone
     - 0.7 s
   * - TUI load until table drawn
     - 9.4 s
   * - Filter logic excluding table rebuild
     - 0.14 s
   * - Clear filter / sort / severity toggle
     - 6 to 9 s
   * - First scroll after rebuild
     - 5 s
   * - RSS after parse / after table drawn
     - 219 MB / 404 MB

Diagnosis
---------

- About 90% of load and 95% of each interactive action was Textual
  ``DataTable.add_row`` plus its deferred ``_update_dimensions`` cell
  measurement. ``DataTable`` virtualises rendering, not population.
- Parse was bound by Python object creation (about 40%: per-match dict,
  ``Message``, ``FileRef``, metadata dict). Regex was under 20%, I/O
  about 6%.
- Memory per ``Message`` was about 820 B:

  - metadata dict: 184 B
  - ``raw_text``: 167 B
  - slots object: 104 B
  - ``content``: 86 B (always a substring of ``raw_text``)
  - unshared ``message_id`` / ``category`` / path strings: about 144 B

What was changed
----------------

- **Plugin API 2**: ``load_and_parse`` returns ``Iterator[Message]``.
  API 1 plugins returning lists keep working. See :doc:`plugin-api-2`.
- **Message model**: ``Message`` and ``FileRef`` are
  ``@dataclass(slots=True)`` (``FileRef`` is frozen).
  ``__post_init__`` coerces ``start_line``, ``end_line`` and ``line`` to
  ``int``. No Pydantic on the hot path.
- **Windowed table**: the TUI populates only a window of rows around the
  cursor, ``max(3 × visible rows, 200)``, and re-windows centred on the
  cursor as it moves. The subtitle shows ``row i of N``.
- **Waivers**: matched once per message; redundant list copies removed.

Benchmarks
----------

- ``tools/bench/gen_xcelium_log.py``: synthetic log generator.
- ``tools/bench/run_bench.py``: size sweep, fresh subprocess per size,
  current RSS from ``/proc/self/statm`` plus peak.
- ``tools/bench/bench_message.py``: ``Message`` construction cost.

Current numbers
---------------

.. list-table:: 200k messages
   :header-rows: 1

   * - Action
     - Before
     - After
   * - Load
     - 9.7 s
     - 0.24 s
   * - Clear filter
     - 8.87 s
     - 0.12 s
   * - Sort
     - 8.93 s
     - 0.26 s
   * - Severity toggle
     - 6.66 s
     - 0.18 s
   * - RSS after table drawn
     - 332 MB
     - 158 MB

At 1M messages:

- parse: 3.5 s
- load: 0.49 s
- filter / sort / toggles: 0.36 to 0.70 s
- RSS: about 550 MB after parse, 660 MB at end

A column store was also evaluated and not adopted; see
:doc:`store-investigation`.
