# Sawmill performance: findings and plan

Working notes for making chip-level logs (100 MB+, 1M+ messages) usable.
Supersedes the earlier streaming spec, whose diagnosis was wrong.

## 1. What was measured (2026-11-04)

Synthetic Xcelium log, 200k messages, 24 MB, Python 3.14, Textual DataTable.

| Step | Time |
|---|---|
| Plugin parse alone | 0.7 s |
| TUI load until table drawn | 9.4 s |
| Filter logic excluding table rebuild | 0.14 s |
| Clear filter / sort / severity toggle | 6 to 9 s |
| First scroll after rebuild | 5 s |
| RSS after parse / after table populated | 219 MB / 404 MB |

- About 90 % of load time and 95 % of every interactive action is spent
  inside `DataTable.add_row` and the deferred `_update_dimensions` pass that
  measures every cell. DataTable virtualises rendering, not population.
- Parse is bound by Python object creation (dict per match, Message, FileRef,
  metadata dict), not regex (under 20 %) or I/O (about 6 %).
- Memory per Message was about 820 B: 184 B metadata dict, 167 B raw_text,
  104 B slots object, 86 B content (always a substring of raw_text), plus
  unshared copies of message_id, category and file path.

## 2. Done

- Plugin hook `load_and_parse` returns `Iterator[Message]` (plugin API 2).
  `sawmill.core.plugin.load_messages()` wraps list-returning plugins.
  Plugins open the file eagerly so errors surface at call time.
- `Message` and `FileRef` are `@dataclass(slots=True)` with int coercion.
- Xcelium plugin: single regex, no per-match dict, interned strings, shared
  per-tool metadata dict. 820 B to 520 B per message, output identical.
- Benchmarks in `tools/bench/` report current and peak RSS and go through
  the real filter helpers.

## 3. In progress

- Windowed DataTable: the table holds a window of rows around the cursor;
  `_filtered_messages` stays the full list. Branch `perf/windowed-table`.
- One waiver match per message; redundant list copies removed.

## 4. Next: store investigation

After the view is fixed, measure a real 130 MB log. If memory is still the
complaint, compare on a branch:

- Intern-only (current design, about 500 B/message, no new dependency).
- DuckDB: columnar, dictionary-encoded, vectorised filter/sort/group-by,
  native regex, spill to disk, `LIMIT/OFFSET` paging. Roughly 150 to 250 MB
  per 1M messages. Cost: 50 MB wheel, 100 ms import, SQL in the app, waiver
  and suppression logic expressed as predicates.
- Polars: same idea, dataframe API, lighter, no spill.
- Hand-rolled columnar (int arrays plus byte offsets, text re-read from
  mmap): about 40 B/message but a third plugin contract and binary-mode
  offsets in every plugin. Only if the above are insufficient.

Decide with numbers from the real log, not estimates.

## 5. Dropped

Background parse thread, stats-only mode, Rust hot loop and FSM preamble
matcher are parked. Parse is under 10 % of load; none of these move the
user-visible numbers until the view and store are settled.
