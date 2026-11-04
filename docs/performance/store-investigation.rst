Column-store investigation
==========================

A spike tested whether a column store would beat a list of ``Message``
objects. The code lives on branch ``spike/duckdb-store``
(``tools/bench/store_spike.py``).

Stores compared
---------------

Three stores behind one query interface:

- **List**: list of ``Message`` (today).
- **DuckDB**: in-memory table, ingested in 50k-row batches via pyarrow.
  ``executemany`` was unusable (25 s per 50k rows).
- **Polars**: DataFrame built from dicts of columns per batch.

Pandas was ruled out up front: per-row string handling is Python
objects anyway, and the wheel is heavy.

Results
-------

1M messages, 128 MB log. "DuckDB file" is file-backed with a 256 MB
memory limit and late materialisation.

.. list-table::
   :header-rows: 1

   * -
     - List
     - DuckDB in-memory
     - DuckDB file
     - Polars
   * - Ingest
     - 3.56 s
     - 4.03 s
     - 3.87 s
     - 2.33 s
   * - Time to first batch
     - 0.15 s
     - 0.16 s
     - 0.18 s
     - 0.12 s
   * - RSS after ingest
     - 531 MB
     - 495 MB
     - 294 MB
     - 423 MB
   * - Severity filter
     - 22 ms
     - 4 ms
     - 3 ms
     - 6 ms
   * - ID glob
     - 200 ms
     - 1 ms
     - 1 ms
     - 6 ms
   * - Regex (common pattern)
     - 439 ms
     - 19 ms
     - 22 ms
     - 7 ms
   * - ID counts (stats)
     - 46 ms
     - 3 ms
     - 1 ms
     - 1 ms
   * - Sort by ID count + page of 200
     - 398 ms
     - 113 ms
     - 124 ms
     - 32 ms
   * - Combined keystroke (filter + sort + page)
     - 389 ms
     - 35 ms
     - 36 ms
     - 12 ms

Other findings
--------------

- With a 256 MB ``memory_limit``, a full-row ``ORDER BY`` raised
  ``OutOfMemoryException`` even at 200k. Sorting only key columns, then
  joining back the 200 page rows (late materialisation), fixed it and
  was 5 to 10× faster generally.
- Without a limit and without late materialisation, RSS reached 2.4 GB.
- Parsing to ``Message`` costs about 0.8 s per 1M over yielding tuples
  (2.58 vs 1.78 s). Ingest only improves if plugins yield tuples.
- Import time (warm): duckdb 45 ms, polars 48 ms, pyarrow 12 ms.
- Installed size: duckdb about 65 MB, pyarrow about 165 MB (needed for
  DuckDB ingest), polars about 180 MB.

Awkward points
--------------

- Regex dialect changes from Python ``re`` to RE2 (DuckDB) or Rust regex
  (Polars): no backreferences or lookaround. Saved filters and waiver
  content patterns could break.
- Waivers would become a table joined on ``message_id`` with
  ``regexp_matches(raw_text, p, 's')``.
- Suppressions become ``message_id IN (...)`` and
  ``NOT regexp_matches``.
- The TUI, waiver generation and export hold ``Message`` objects and
  would move to row indexes.
- ``metadata`` has no column.
- A tuple-yielding plugin hook is needed to realise the ingest gain.

Recommendation
--------------

Not adopted.

- The windowed view removed the user-visible problem.
- A store buys 10× faster keystrokes on any backend, but only
  file-backed DuckDB with a limit saves memory (about 45%).
- Revisit only if a real 130 MB log shows memory is still the complaint,
  or sub-50 ms filtering becomes a feature. File-backed DuckDB is then
  the path.

Parked alternatives:

- background parse thread
- Rust inner loop
- hand-rolled columnar arrays with byte offsets (about 40 B per message,
  but a third plugin contract)
