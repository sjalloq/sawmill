# Sawmill - Implementation Tasks

This document breaks down implementation into discrete, testable tasks. Each task is designed to:
- Fit within a single context window
- Have clear success criteria
- Include specific tests that must pass before proceeding
- Be implementable by an automated agent (ralph loop) without UX decisions

**Note:** TUI tasks (Stage 8) are marked as "Human-Guided" and should not be attempted by the ralph loop.

---

## Stage 1: Project Setup and Data Model Interfaces

### Task 1.0: Test Infrastructure

**Objective:** Set up shared test fixtures and utilities for consistent testing.

**Deliverables:**
- `tests/conftest.py` with common fixtures
- Pytest markers for categorizing tests (slow, integration)
- Shared fixtures: `vivado_log`, `small_log`, `empty_log`, `large_log`

**Success Criteria:**
- [ ] `pytest --collect-only` shows fixtures available
- [ ] Fixtures work in other test files via import

**Tests:**
```python
# tests/conftest.py
"""Shared pytest fixtures for Sawmill tests."""

import pytest
from pathlib import Path


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def vivado_log(project_root):
    """Full Vivado log file for integration tests."""
    return project_root / "examples/vivado/vivado.log"


@pytest.fixture
def small_log(tmp_path):
    """Minimal multi-format log for unit tests."""
    content = """\
INFO: [Synth 8-6157] synthesizing module 'top' [/path/file.v:10]
WARNING: [Vivado 12-3523] Component name change
  Additional detail line
  Another detail line
CRITICAL WARNING: [Constraints 18-4427] Override warning
ERROR: [Route 35-9] Routing failed
Plain text line with no format
"""
    f = tmp_path / "test.log"
    f.write_text(content)
    return f


@pytest.fixture
def empty_log(tmp_path):
    """Empty log file."""
    f = tmp_path / "empty.log"
    f.write_text("")
    return f


@pytest.fixture
def large_log(tmp_path):
    """100k line log file for performance tests."""
    f = tmp_path / "large.log"
    lines = [f"INFO: [Test {i % 100}-{i}] Message number {i}" for i in range(100000)]
    f.write_text("\n".join(lines))
    return f


# Pytest markers
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
```

---

### Task 1.1: Project Scaffolding

**Objective:** Create the basic project structure with proper Python packaging.

**Deliverables:**
- Directory structure as defined in PRD Technical Architecture
- Empty `__init__.py` files in all packages
- Basic `__main__.py` entry point with rich-click CLI skeleton

**Success Criteria:**
- [ ] `pip install -e .` succeeds
- [ ] `python -m sawmill --help` runs without errors
- [ ] All imports resolve correctly

**Tests:**
```python
# tests/test_project_setup.py
def test_package_imports():
    """All core packages should be importable."""
    import sawmill
    import sawmill.core
    import sawmill.tui
    import sawmill.models
    import sawmill.utils

def test_cli_entry_point():
    """CLI should respond to --help."""
    from click.testing import CliRunner
    from sawmill.__main__ import cli
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'sawmill' in result.output.lower()
```

---

### Task 1.2: Data Model Interfaces

**Objective:** Create the data model interfaces (contracts) that plugins will instantiate.

**Deliverables:**
- `sawmill/models/message.py` with `Message`, `FileRef`
- `sawmill/models/filter_def.py` with `FilterDefinition`
- `sawmill/models/waiver.py` with `Waiver`, `WaiverFile`
- Regex validation on `FilterDefinition.pattern` field

**Note:** These are interface definitions. The base app defines them but does NOT instantiate `Message` - that's the plugin's job. The `Message` class represents a logical message (single or multi-line) - the orchestrator doesn't care about line grouping.

**Success Criteria:**
- [ ] All models can be instantiated with required fields
- [ ] Optional fields default to `None`
- [ ] Invalid regex patterns raise validation errors
- [ ] `Message.matches_filter()` works correctly
- [ ] Equality comparison works correctly

**Tests:**
```python
# tests/models/test_message.py
from sawmill.models.message import Message, FileRef

def test_message_single_line():
    """Single-line message has same start and end line."""
    msg = Message(
        start_line=1,
        end_line=1,
        raw_text="ERROR: [Test 1-1] error msg",
        content="error msg"
    )
    assert msg.start_line == 1
    assert msg.end_line == 1
    assert msg.severity is None  # Plugin didn't set it

def test_message_with_metadata():
    """Message with all metadata populated."""
    msg = Message(
        start_line=5,
        end_line=5,
        raw_text="WARNING: [Vivado 12-3523] deprecated",
        content="deprecated",
        severity="warning",
        message_id="Vivado 12-3523",
        category="general"
    )
    assert msg.severity == "warning"
    assert msg.message_id == "Vivado 12-3523"

def test_message_multiline():
    """Multi-line message spans multiple lines."""
    msg = Message(
        start_line=10,
        end_line=13,
        raw_text="Error: timing violation\n  slack: -0.5ns\n  path: clk -> reg\n  suggestion: fix it",
        content="timing violation",
        severity="error"
    )
    assert msg.start_line == 10
    assert msg.end_line == 13
    assert "\n" in msg.raw_text

def test_message_matches_filter():
    """Message.matches_filter should match against raw_text."""
    msg = Message(
        start_line=1,
        end_line=2,
        raw_text="Error: timing violation\n  slack: -0.5ns",
        content="timing violation"
    )
    assert msg.matches_filter(r"slack.*-\d+\.\d+") is True
    assert msg.matches_filter(r"DRC violation") is False

def test_file_ref_creation():
    ref = FileRef(path="/path/to/file.v", line=53)
    assert ref.path == "/path/to/file.v"
    assert ref.line == 53


# tests/models/test_filter_def.py
import pytest
from sawmill.models.filter_def import FilterDefinition

def test_filter_creation():
    f = FilterDefinition(
        id="test-filter",
        name="Test Filter",
        pattern=r"Error:\s+\w+",
        enabled=True
    )
    assert f.id == "test-filter"
    assert f.enabled is True

def test_invalid_regex_rejected():
    with pytest.raises(ValueError):
        FilterDefinition(
            id="bad",
            name="Bad",
            pattern=r"[invalid(regex",  # Unclosed bracket
            enabled=True
        )

def test_filter_toggle():
    f = FilterDefinition(id="t", name="T", pattern="test", enabled=True)
    f.enabled = False
    assert f.enabled is False

def test_filter_source_tracking():
    f = FilterDefinition(id="t", name="T", pattern="test", enabled=True, source="plugin:vivado")
    assert f.source == "plugin:vivado"
```

---

## Stage 2: Plugin System

### Task 2.1: Plugin Hook Specification

**Objective:** Define the pluggy hook specification for sawmill plugins.

**Deliverables:**
- `sawmill/plugin/__init__.py` with hook markers and base class
- `sawmill/plugin/hookspec.py` with `SawmillHookSpec` class
- All hook definitions with proper signatures

**Note:** Multi-line grouping is handled internally by plugins. The `load_and_parse()` hook returns `list[Message]` where each Message is already a complete logical unit.

**Success Criteria:**
- [ ] Hook specification defines all required hooks
- [ ] `hookimpl` decorator available for plugins
- [ ] `SawmillPlugin` base class provides sensible defaults (returning empty/None)

**Tests:**
```python
# tests/plugin/test_hookspec.py
from pathlib import Path
from sawmill.plugin import SawmillPlugin, hookimpl, SawmillHookSpec

def test_hookspec_defines_required_hooks():
    spec = SawmillHookSpec()
    assert hasattr(spec, 'can_handle')
    assert hasattr(spec, 'load_and_parse')
    assert hasattr(spec, 'get_filters')

def test_base_plugin_has_defaults():
    class TestPlugin(SawmillPlugin):
        name = "test"

    plugin = TestPlugin()
    # Default implementations should return empty/None (opt-out)
    assert plugin.can_handle(Path("test.log")) == 0.0
    assert plugin.load_and_parse(Path("test.log")) == []
    assert plugin.get_filters() == []
```

---

### Task 2.2: Plugin Manager with Entry Point Discovery

**Objective:** Implement plugin discovery via Python entry points.

**Deliverables:**
- `sawmill/core/plugin.py` with `PluginManager` class
- Discovery via `importlib.metadata.entry_points`
- Plugin registration with pluggy
- `PluginConflictError` exception for when >1 plugin has confidence > 0.5

**Success Criteria:**
- [ ] Discovers plugins from `sawmill.plugins` entry point group
- [ ] Registers plugins with pluggy PluginManager
- [ ] Lists available plugins with metadata

**Tests:**
```python
# tests/core/test_plugin_manager.py
from pathlib import Path
import pluggy
from sawmill.core.plugin import PluginManager
from sawmill.plugin import SawmillPlugin, hookimpl
from sawmill.models.filter_def import FilterDefinition

class MockPlugin(SawmillPlugin):
    name = "mock"
    version = "1.0.0"

    @hookimpl
    def can_handle(self, path):
        return 0.9 if "mock" in str(path).lower() else 0.0

    @hookimpl
    def get_filters(self):
        return [FilterDefinition(id="mock", name="Mock", pattern="MOCK", enabled=True)]

def test_register_plugin():
    manager = PluginManager()
    manager.register(MockPlugin())

    assert "mock" in manager.list_plugins()

def test_plugin_hooks_called():
    manager = PluginManager()
    manager.register(MockPlugin())

    results = manager.pm.hook.can_handle(path=Path("mock.log"))
    assert 0.9 in results
```

---

### Task 2.3: Auto-Detection and Plugin Selection

**Objective:** Automatically detect log type and select appropriate plugin.

**Deliverables:**
- Method: `PluginManager.auto_detect(path) -> Optional[str]`
- Method: `PluginManager.get_plugin(name) -> SawmillPlugin`
- CLI option: `--plugin <name>` to force specific plugin
- Conflict detection when >1 plugin has confidence > 0.5

**Success Criteria:**
- [ ] Selects plugin with highest confidence score
- [ ] **Raises NoPluginFoundError if no plugin has confidence > 0.5**
- [ ] **Raises PluginConflictError if >1 plugin has confidence > 0.5**
- [ ] `--plugin vivado` forces Vivado plugin (bypasses auto-detect)

**Tests:**
```python
# tests/core/test_plugin_autodetect.py
from pathlib import Path
import pytest
from sawmill.core.plugin import PluginConflictError, NoPluginFoundError, PluginManager
from sawmill.plugin import SawmillPlugin, hookimpl

def test_auto_detect_selects_highest_confidence():
    manager = PluginManager()

    class LowPlugin(SawmillPlugin):
        name = "low"
        @hookimpl
        def can_handle(self, path):
            return 0.3

    class HighPlugin(SawmillPlugin):
        name = "high"
        @hookimpl
        def can_handle(self, path):
            return 0.9

    manager.register(LowPlugin())
    manager.register(HighPlugin())

    selected = manager.auto_detect(Path("test.log"))
    assert selected == "high"

def test_auto_detect_errors_when_no_plugin_matches():
    """If no plugin has confidence > 0.5, raise error."""
    manager = PluginManager()

    class WeakPlugin(SawmillPlugin):
        name = "weak"
        @hookimpl
        def can_handle(self, path):
            return 0.2

    manager.register(WeakPlugin())

    with pytest.raises(NoPluginFoundError) as exc:
        manager.auto_detect(Path("test.log"))
    assert "no plugin" in str(exc.value).lower()

def test_auto_detect_errors_on_conflict():
    """If multiple plugins both return >0.5, raise error."""
    manager = PluginManager()

    class PluginA(SawmillPlugin):
        name = "plugin_a"
        @hookimpl
        def can_handle(self, path):
            return 0.8

    class PluginB(SawmillPlugin):
        name = "plugin_b"
        @hookimpl
        def can_handle(self, path):
            return 0.75

    manager.register(PluginA())
    manager.register(PluginB())

    with pytest.raises(PluginConflictError) as exc:
        manager.auto_detect(Path("test.log"))
    assert "plugin_a" in str(exc.value) or "plugin_b" in str(exc.value)
```

---

### Task 2.4: Built-in Vivado Plugin

**Objective:** Create the reference Vivado plugin as a built-in.

**Deliverables:**
- `sawmill/plugins/vivado.py` with `VivadoPlugin` class
- All hooks implemented for Vivado log format:
  - `can_handle()` - detect Vivado logs
  - `load_and_parse()` - load file, parse, and group into `list[Message]`
  - `get_filters()` - comprehensive filter set
  - `extract_file_reference()` - extract file:line references
- Register as built-in plugin (not via entry point)

**Note:** The plugin handles multi-line grouping internally. It returns `list[Message]` where each Message is a complete logical unit.

**Success Criteria:**
- [ ] Detects Vivado logs with high confidence
- [ ] Returns `list[Message]` with proper start_line/end_line for multi-line messages
- [ ] Correctly extracts severity, message_id, content
- [ ] Provides comprehensive filter set
- [ ] Extracts file references from messages

**Tests:**
```python
# tests/plugins/test_vivado.py
from pathlib import Path
from sawmill.plugins.vivado import VivadoPlugin

def test_vivado_detects_vivado_logs(tmp_path):
    plugin = VivadoPlugin()
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2 (64-bit)\nINFO: [Synth 8-6157] test")

    confidence = plugin.can_handle(log_file)
    assert confidence >= 0.9

def test_vivado_does_not_detect_other_logs(tmp_path):
    plugin = VivadoPlugin()
    log_file = tmp_path / "other.log"
    log_file.write_text("Some random log file content")

    confidence = plugin.can_handle(log_file)
    assert confidence < 0.5

def test_vivado_load_and_parse(tmp_path):
    plugin = VivadoPlugin()
    log_file = tmp_path / "vivado.log"
    log_file.write_text("WARNING: [Vivado 12-3523] Component name change\nINFO: [Synth 8-1] Done\n")

    messages = plugin.load_and_parse(log_file)

    assert len(messages) == 2
    assert messages[0].severity == "warning"
    assert messages[0].message_id == "Vivado 12-3523"
    assert messages[1].severity == "info"

def test_vivado_parses_critical_warning(tmp_path):
    plugin = VivadoPlugin()
    log_file = tmp_path / "vivado.log"
    log_file.write_text("CRITICAL WARNING: [Constraints 18-4427] Override warning\n")

    messages = plugin.load_and_parse(log_file)

    assert messages[0].severity == "critical_warning"
    assert messages[0].message_id == "Constraints 18-4427"

def test_vivado_extracts_file_reference():
    plugin = VivadoPlugin()

    ref = plugin.extract_file_reference("synthesizing module 'top' [/path/to/file.v:53]")

    assert ref is not None
    assert ref.path == "/path/to/file.v"
    assert ref.line == 53

def test_vivado_filters_cover_common_cases():
    plugin = VivadoPlugin()
    filters = plugin.get_filters()

    filter_ids = [f.id for f in filters]
    assert "errors" in filter_ids
    assert "critical-warnings" in filter_ids
    assert "warnings" in filter_ids

def test_vivado_multiline_message(tmp_path):
    """Plugin should group multi-line messages into single Message objects."""
    plugin = VivadoPlugin()
    log_file = tmp_path / "vivado.log"
    # Vivado table output spans multiple lines
    log_file.write_text("""WARNING: [Vivado 12-3523] Some warning
  with continuation line
  and another line
INFO: [Synth 8-1] Next message
""")

    messages = plugin.load_and_parse(log_file)

    # Should be 2 messages, not 4 lines
    assert len(messages) == 2
    # First message should span multiple lines
    assert messages[0].start_line == 1
    assert messages[0].end_line >= 3  # At least 3 lines
    assert "continuation" in messages[0].raw_text
```

---

### Task 2.5: Plugin Discovery CLI

**Objective:** Implement CLI commands for plugin discovery and introspection.

**Deliverables:**
- `--list-plugins` option to enumerate discovered plugins
- `--show-info` option (with `--plugin`) to display plugin capabilities
- Show: version, hooks implemented, filter counts

**Success Criteria:**
- [ ] `sawmill --list-plugins` shows all installed plugins
- [ ] `sawmill --plugin vivado --show-info` shows Vivado plugin details
- [ ] Output includes plugin version and implemented hooks

**Tests:**
```python
# tests/test_cli_plugin_discovery.py
from click.testing import CliRunner
from sawmill.cli import cli

def test_list_plugins():
    """--list-plugins should enumerate all plugins."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--list-plugins'])

    assert result.exit_code == 0
    assert "vivado" in result.output.lower()

def test_show_plugin_info():
    """--show-info should display plugin capabilities."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--plugin', 'vivado', '--show-info'])

    assert result.exit_code == 0
    assert "vivado" in result.output.lower()

def test_show_info_requires_plugin():
    """--show-info without --plugin should error."""
    runner = CliRunner()
    result = runner.invoke(cli, ['--show-info'])

    # Should fail or provide helpful message
    assert result.exit_code != 0 or "plugin" in result.output.lower()
```

---

## Stage 3: Filter Engine

### Task 3.1: Basic Regex Filter Engine

**Objective:** Implement the core filtering logic that operates on plugin output.

**Deliverables:**
- `sawmill/core/filter.py` with `FilterEngine` class
- Method: `apply_filter(pattern, messages) -> list[Message]`
- Method: `apply_filters(filters, messages, mode='AND'|'OR') -> list[Message]`
- Method: `apply_suppressions(patterns, messages) -> list[Message]`

**Note:** FilterEngine operates on `list[Message]` provided by plugins. Each Message is a complete logical unit.

**Success Criteria:**
- [ ] Single filter correctly matches messages
- [ ] AND mode requires all filters to match
- [ ] OR mode requires any filter to match
- [ ] Suppressions remove matching messages
- [ ] Invalid regex returns empty results with error flag

**Tests:**
```python
# tests/core/test_filter.py
from sawmill.core.filter import FilterEngine
from sawmill.models.message import Message
from sawmill.models.filter_def import FilterDefinition

def test_single_filter_match():
    messages = [
        Message(1, 1, "Error: test", "test", severity="error"),
        Message(2, 2, "Info: test", "test", severity="info"),
        Message(3, 3, "Error: another", "another", severity="error"),
    ]
    engine = FilterEngine()
    results = engine.apply_filter(r"^Error:", messages)

    assert len(results) == 2
    assert all("Error:" in m.raw_text for m in results)

def test_filter_case_insensitive():
    messages = [
        Message(1, 1, "ERROR: test", "test"),
        Message(2, 2, "error: test", "test"),
    ]
    engine = FilterEngine()
    results = engine.apply_filter(r"error:", messages, case_sensitive=False)

    assert len(results) == 2

def test_multiple_filters_and_mode():
    messages = [
        Message(1, 1, "Error: timing slack -0.5", "timing slack -0.5", severity="error"),
        Message(2, 2, "Error: DRC violation", "DRC violation", severity="error"),
        Message(3, 3, "Warning: timing slack -0.2", "timing slack -0.2", severity="warning"),
    ]
    filters = [
        FilterDefinition(id="1", name="Errors", pattern=r"^Error:", enabled=True),
        FilterDefinition(id="2", name="Timing", pattern=r"timing", enabled=True),
    ]

    engine = FilterEngine()
    results = engine.apply_filters(filters, messages, mode='AND')

    assert len(results) == 1  # Only first matches both

def test_multiple_filters_or_mode():
    messages = [
        Message(1, 1, "Error: timing", "timing"),
        Message(2, 2, "Error: DRC", "DRC"),
        Message(3, 3, "Info: done", "done"),
    ]
    filters = [
        FilterDefinition(id="1", name="Timing", pattern=r"timing", enabled=True),
        FilterDefinition(id="2", name="DRC", pattern=r"DRC", enabled=True),
    ]

    engine = FilterEngine()
    results = engine.apply_filters(filters, messages, mode='OR')

    assert len(results) == 2  # First two match

def test_disabled_filters_ignored():
    messages = [Message(1, 1, "Error: test", "test")]
    filters = [
        FilterDefinition(id="1", name="Disabled", pattern=r"Error", enabled=False),
    ]

    engine = FilterEngine()
    results = engine.apply_filters(filters, messages, mode='AND')

    assert len(results) == 1  # Disabled filter doesn't restrict

def test_suppressions_remove_matches():
    messages = [
        Message(1, 1, "Error: important", "important", severity="error"),
        Message(2, 2, "Info: noisy startup", "noisy startup", severity="info"),
        Message(3, 3, "Warning: also important", "also important", severity="warning"),
    ]

    engine = FilterEngine()
    results = engine.apply_suppressions([r"noisy"], messages)

    assert len(results) == 2
    assert all("noisy" not in m.raw_text for m in results)
```

---

### Task 3.2: Filter Statistics

**Objective:** Track and report filter match statistics.

**Deliverables:**
- `FilterStats` dataclass with `total_messages`, `matched_messages`, `match_percentage`
- Method: `FilterEngine.get_stats(filters, messages) -> FilterStats`
- Per-filter match counts

**Success Criteria:**
- [ ] Correctly counts total and matched messages
- [ ] Calculates accurate percentages
- [ ] Provides per-filter breakdown

**Tests:**
```python
# tests/core/test_filter_stats.py
from sawmill.core.filter import FilterEngine, FilterStats
from sawmill.models.message import Message
from sawmill.models.filter_def import FilterDefinition

def test_basic_stats():
    messages = [Message(i, i, f"Line {i}", f"Line {i}") for i in range(100)]
    filters = [FilterDefinition(id="1", name="Even", pattern=r"Line [02468]$", enabled=True)]

    engine = FilterEngine()
    stats = engine.get_stats(filters, messages)

    assert stats.total_messages == 100
    assert stats.matched_messages == 5  # Lines 0, 2, 4, 6, 8

def test_stats_percentage():
    messages = [Message(i, i, "Match" if i < 25 else "NoMatch", "...") for i in range(100)]
    filters = [FilterDefinition(id="1", name="Match", pattern=r"^Match$", enabled=True)]

    engine = FilterEngine()
    stats = engine.get_stats(filters, messages)

    assert stats.match_percentage == 25.0

def test_per_filter_stats():
    messages = [
        Message(1, 1, "Error: test", "test", severity="error"),
        Message(2, 2, "Warning: test", "test", severity="warning"),
        Message(3, 3, "Info: test", "test", severity="info"),
    ]
    filters = [
        FilterDefinition(id="errors", name="Errors", pattern=r"^Error:", enabled=True),
        FilterDefinition(id="warnings", name="Warnings", pattern=r"^Warning:", enabled=True),
    ]

    engine = FilterEngine()
    stats = engine.get_stats(filters, messages)

    assert stats.per_filter["errors"] == 1
    assert stats.per_filter["warnings"] == 1
```

---

## Stage 4: CLI Streaming Interface

### Task 4.1: Basic CLI with Stdout Output

**Objective:** Create a CLI that reads a log file, delegates to plugin, and streams filtered output.

**Deliverables:**
- `sawmill/cli.py` with main CLI using rich-click
- Accept log file as positional argument
- `--severity` option to filter by severity level
- `--filter` option for regex pattern (include matches)
- `--suppress` option for regex pattern (exclude matches) - can be repeated
- `--suppress-id` option for message ID (exclude by ID) - can be repeated
- `--plugin` option to force specific plugin
- Stream matching lines to stdout with Rich formatting

**Note:** The CLI orchestrates: discover plugin -> call plugin.load_and_parse() -> apply filters/suppressions -> display. A plugin is required - no plugin means error. Suppressions are for display filtering (hiding noise), distinct from waivers (CI acceptance).

**Success Criteria:**
- [ ] `sawmill logfile.log` auto-detects plugin and processes file
- [ ] `sawmill logfile.log` errors if no plugin can handle the file
- [ ] `sawmill logfile.log --severity error` filters to errors
- [ ] `sawmill logfile.log --filter "pattern"` filters by regex
- [ ] `sawmill logfile.log --suppress "pattern"` hides matching messages
- [ ] `sawmill logfile.log --suppress-id "ID"` hides messages by ID
- [ ] Multiple `--suppress` options accumulate
- [ ] Output is colorized based on severity

**Tests:**
```python
# tests/test_cli.py
from click.testing import CliRunner
from sawmill.cli import cli

def test_cli_basic_output(tmp_path):
    """With Vivado plugin, basic output should work."""
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2\nINFO: [Test 1-1] message\nERROR: [Test 2-1] error\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file)])

    assert result.exit_code == 0

def test_cli_errors_without_plugin(tmp_path):
    """Without matching plugin, should error."""
    log_file = tmp_path / "unknown.log"
    log_file.write_text("some random content that no plugin recognizes\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file)])

    assert result.exit_code != 0
    assert "plugin" in result.output.lower()

def test_cli_regex_filter(tmp_path):
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2\nINFO: timing slack -0.5\nINFO: DRC violation\nINFO: timing slack -0.2\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--filter', 'timing'])

    assert result.exit_code == 0
    assert "timing" in result.output
    assert "DRC" not in result.output

def test_cli_with_plugin(tmp_path):
    """With Vivado plugin, severity filter should work."""
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2\nINFO: [Synth 8-1] info\nERROR: [DRC 1-1] error\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--plugin', 'vivado', '--severity', 'error'])

    assert result.exit_code == 0
    assert "ERROR" in result.output

def test_cli_suppress_pattern(tmp_path):
    """--suppress should hide matching messages."""
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2\nINFO: [Synth 8-1] starting\nINFO: [Synth 8-2] noisy message\nERROR: [DRC 1-1] real error\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--suppress', 'noisy'])

    assert result.exit_code == 0
    assert "noisy" not in result.output
    assert "real error" in result.output

def test_cli_suppress_id(tmp_path):
    """--suppress-id should hide messages by ID."""
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2\nINFO: [Common 17-55] suppress this\nERROR: [DRC 1-1] keep this\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--suppress-id', 'Common 17-55'])

    assert result.exit_code == 0
    assert "Common 17-55" not in result.output
    assert "DRC 1-1" in result.output

def test_cli_multiple_suppress(tmp_path):
    """Multiple --suppress options should accumulate."""
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2\nINFO: [A 1-1] noise1\nINFO: [B 2-1] noise2\nERROR: [C 3-1] important\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--suppress', 'noise1', '--suppress', 'noise2'])

    assert result.exit_code == 0
    assert "noise1" not in result.output
    assert "noise2" not in result.output
    assert "important" in result.output
```

---

### Task 4.2: Output Formats

**Objective:** Support multiple output formats (text, JSON, count).

**Deliverables:**
- `--format` option with choices: text, json, count
- Text format: human-readable with colors (default)
- JSON format: one JSON object per line (JSONL)
- Count format: summary statistics only

**Success Criteria:**
- [ ] `--format text` outputs colored, readable text
- [ ] `--format json` outputs valid JSONL
- [ ] `--format count` outputs summary: `errors=N warnings=M info=K`

**Tests:**
```python
# tests/test_cli_formats.py
import json
from click.testing import CliRunner
from sawmill.cli import cli

def test_json_format(tmp_path):
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] message\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--plugin', 'vivado', '--format', 'json'])

    assert result.exit_code == 0
    # Should have JSON output
    lines = [l for l in result.output.strip().split('\n') if l.startswith('{')]
    assert len(lines) > 0
    data = json.loads(lines[-1])
    assert 'severity' in data or 'content' in data

def test_count_format(tmp_path):
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2\nERROR: [E1 1-1] e1\nERROR: [E2 1-2] e2\nWARNING: [W1 2-1] w1\nINFO: [I1 3-1] i1\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--plugin', 'vivado', '--format', 'count'])

    assert result.exit_code == 0
    output_lower = result.output.lower()
    assert "error" in output_lower
```

---

### Task 4.3: Message ID Filtering

**Objective:** Support filtering by message IDs (requires plugin).

**Deliverables:**
- `--id` option to filter by message ID pattern
- Support wildcards: `--id "Synth 8-*"` matches all Synth 8-xxxx
- `--category` option for high-level categories

**Success Criteria:**
- [ ] `--id "Vivado 12-3523"` matches exact ID
- [ ] `--id "Synth 8-*"` matches all Synth 8-xxxx messages
- [ ] `--category timing` matches timing-related messages

**Tests:**
```python
# tests/test_cli_id_filter.py
from click.testing import CliRunner
from sawmill.cli import cli

def test_exact_id_filter(tmp_path):
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2\nWARNING: [Vivado 12-3523] msg1\nWARNING: [Vivado 12-4739] msg2\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--plugin', 'vivado', '--id', 'Vivado 12-3523'])

    assert "12-3523" in result.output
    assert "12-4739" not in result.output

def test_wildcard_id_filter(tmp_path):
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2\nINFO: [Synth 8-6157] a\nINFO: [Synth 8-6155] b\nINFO: [Vivado 12-1] c\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--plugin', 'vivado', '--id', 'Synth 8-*'])

    assert "8-6157" in result.output
    assert "8-6155" in result.output
    # Vivado 12-1 should not be in filtered output
```

---

### Task 4.4: CLI Integration Tests

**Objective:** Verify full pipeline works end-to-end with real Vivado logs.

**Deliverables:**
- Integration tests using `examples/vivado/vivado.log`
- Test full pipeline: CLI -> plugin.load_and_parse() -> filter -> format

**Success Criteria:**
- [ ] Full pipeline executes without error
- [ ] Output matches expected format
- [ ] All filter options work together correctly

**Tests:**
```python
# tests/test_cli_integration.py
from click.testing import CliRunner
from sawmill.cli import cli
import pytest

@pytest.mark.integration
def test_vivado_log_loads_successfully(vivado_log):
    """Full Vivado log should load and process without errors."""
    runner = CliRunner()
    result = runner.invoke(cli, [str(vivado_log), '--plugin', 'vivado', '--format', 'count'])

    assert result.exit_code == 0

@pytest.mark.integration
def test_vivado_severity_filter(vivado_log):
    """Severity filtering should work on real Vivado logs."""
    runner = CliRunner()
    result = runner.invoke(cli, [str(vivado_log), '--plugin', 'vivado', '--severity', 'error,critical_warning'])

    assert result.exit_code == 0
    # Should not contain plain INFO messages
    lines = [l for l in result.output.split('\n') if l.strip()]
    # Filter out any status/header lines, check actual log lines don't have INFO severity

@pytest.mark.integration
def test_vivado_combined_filters(vivado_log):
    """Multiple filters should work together."""
    runner = CliRunner()
    result = runner.invoke(cli, [
        str(vivado_log),
        '--plugin', 'vivado',
        '--severity', 'warning',
        '--filter', 'timing',
        '--format', 'count'
    ])

    assert result.exit_code == 0
```

---

## Stage 5: Configuration System

### Task 5.1: TOML Configuration Loader

**Objective:** Implement configuration file parsing.

**Deliverables:**
- `sawmill/core/config.py` with `ConfigLoader` class
- `Config` dataclass with all settings including `suppress` section
- Parse and validate TOML configuration
- `ConfigError` exception for malformed TOML

**Note:** The `[suppress]` section is for display filtering (hiding noise), distinct from waivers (CI acceptance). See PRD "Suppressions vs Waivers" section.

**Success Criteria:**
- [ ] Parses valid TOML files correctly
- [ ] Parses `[suppress]` patterns and message_ids
- [ ] Returns sensible defaults for missing keys
- [ ] Handles malformed TOML with clear errors (including line number)

**Tests:**
```python
# tests/core/test_config.py
import pytest
from sawmill.core.config import ConfigLoader, ConfigError

def test_load_basic_config(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('''
[general]
default_plugin = "vivado"

[output]
color = true
format = "text"
''')

    loader = ConfigLoader()
    config = loader.load(config_file)

    assert config.general.default_plugin == "vivado"
    assert config.output.color is True

def test_default_values():
    loader = ConfigLoader()
    config = loader.load(None)  # No file

    assert config.output.format == "text"  # default
    assert config.output.color is True  # default

def test_malformed_toml_error_message(tmp_path):
    """Malformed TOML should give line number in error."""
    bad_config = tmp_path / "bad.toml"
    bad_config.write_text('[section\nkey = "unclosed')

    loader = ConfigLoader()
    with pytest.raises(ConfigError) as exc:
        loader.load(bad_config)
    assert "line" in str(exc.value).lower()

def test_suppress_config(tmp_path):
    """Suppress patterns should be loaded from config."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('''
[suppress]
patterns = ["^INFO: \\\\[.*\\\\] Launching", "DEBUG:"]
message_ids = ["Common 17-55", "Vivado 12-3523"]
''')

    loader = ConfigLoader()
    config = loader.load(config_file)

    assert len(config.suppress.patterns) == 2
    assert "Common 17-55" in config.suppress.message_ids
```

---

### Task 5.2: Configuration Discovery and Merging

**Objective:** Implement hierarchical configuration discovery and merging.

**Deliverables:**
- Method: `ConfigLoader.discover_configs(start_path) -> List[Path]`
- Method: `ConfigLoader.load_merged(start_path) -> Config`
- Precedence: CLI > local > git root > user > defaults
- `sawmill/utils/git.py` with `find_git_root()` function

**Success Criteria:**
- [ ] Finds configs in correct precedence order
- [ ] Later configs override earlier values
- [ ] Unspecified values fall through
- [ ] Git root detection works correctly

**Tests:**
```python
# tests/core/test_config_discovery.py
from sawmill.core.config import ConfigLoader

def test_precedence_order(tmp_path, monkeypatch):
    # Local config
    (tmp_path / "sawmill.toml").write_text('[output]\nformat = "json"\n')

    # User config
    user_config = tmp_path / ".config" / "sawmill"
    user_config.mkdir(parents=True)
    (user_config / "config.toml").write_text('[output]\nformat = "text"\ncolor = false\n')

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))

    loader = ConfigLoader()
    config = loader.load_merged(tmp_path)

    assert config.output.format == "json"  # local overrides user
    assert config.output.color is False  # from user config

# tests/utils/test_git.py
def test_find_git_root_in_repo(tmp_path, monkeypatch):
    """Should find .git directory."""
    (tmp_path / ".git").mkdir()
    subdir = tmp_path / "src" / "deep"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)

    from sawmill.utils.git import find_git_root
    assert find_git_root() == tmp_path

def test_find_git_root_not_in_repo(tmp_path, monkeypatch):
    """Should return None outside git repo."""
    monkeypatch.chdir(tmp_path)

    from sawmill.utils.git import find_git_root
    assert find_git_root() is None

def test_git_root_env_override(tmp_path, monkeypatch):
    """SAWMILL_GIT_ROOT should override detection."""
    override_path = tmp_path / "override"
    override_path.mkdir()
    monkeypatch.setenv("SAWMILL_GIT_ROOT", str(override_path))

    from sawmill.utils.git import find_git_root
    assert find_git_root() == override_path
```

---

## Stage 6: Waiver System

**Note:** Waivers are for **CI acceptance** (pass/fail decisions with audit trail). They are distinct from **suppressions** which are for display filtering (hiding noise). See PRD "Suppressions vs Waivers" section.

### Task 6.1: Waiver Data Model and Parser

**Objective:** Define waiver data structures and parse waiver files.

**Deliverables:**
- Update `sawmill/models/waiver.py` with complete `Waiver`, `WaiverFile` classes
- `sawmill/core/waiver.py` with `WaiverLoader` class
- Support all waiver types: id, pattern, file, hash
- `WaiverValidationError` exception

**Success Criteria:**
- [ ] Parse valid waiver TOML files
- [ ] Validate waiver entries (required fields, valid patterns)
- [ ] Handle malformed waiver files with clear errors

**Tests:**
```python
# tests/core/test_waiver.py
import pytest
from sawmill.core.waiver import WaiverLoader, WaiverValidationError

def test_parse_waiver_file(tmp_path):
    waiver_file = tmp_path / "waivers.toml"
    waiver_file.write_text('''
[metadata]
tool = "vivado"

[[waiver]]
type = "id"
pattern = "Vivado 12-3523"
reason = "Intentional"
author = "test"
date = "2026-01-18"
''')

    loader = WaiverLoader()
    waivers = loader.load(waiver_file)

    assert len(waivers.waivers) == 1
    assert waivers.waivers[0].type == "id"
    assert waivers.waivers[0].pattern == "Vivado 12-3523"

def test_invalid_waiver_rejected(tmp_path):
    waiver_file = tmp_path / "bad.toml"
    waiver_file.write_text('''
[[waiver]]
type = "id"
# Missing required fields: pattern, reason
''')

    loader = WaiverLoader()
    with pytest.raises(WaiverValidationError):
        loader.load(waiver_file)
```

---

### Task 6.2: Waiver Matching Engine

**Objective:** Implement waiver matching against log messages.

**Deliverables:**
- `sawmill/core/waiver.py` with `WaiverMatcher` class
- Method: `is_waived(message, waivers) -> Optional[Waiver]`
- Support all match types with correct priority

**Success Criteria:**
- [ ] ID patterns match message IDs
- [ ] Regex patterns match message content
- [ ] File patterns match source file paths
- [ ] Hash matches exact message content
- [ ] Priority order: hash > id > pattern > file

**Tests:**
```python
# tests/core/test_waiver_matching.py
from sawmill.core.waiver import WaiverMatcher
from sawmill.models.waiver import Waiver
from sawmill.models.message import ParsedMessage

def test_id_match():
    waiver = Waiver(type="id", pattern="Vivado 12-3523", reason="test", author="test", date="2026-01-18")
    message = ParsedMessage(1, "WARNING: [Vivado 12-3523] some message", "some message", message_id="Vivado 12-3523")

    matcher = WaiverMatcher([waiver])
    result = matcher.is_waived(message)

    assert result == waiver

def test_pattern_match():
    waiver = Waiver(type="pattern", pattern="usb_fifo_clk", reason="async clock", author="test", date="2026-01-18")
    message = ParsedMessage(1, "WARNING: set_input_delay usb_fifo_clk", "set_input_delay usb_fifo_clk")

    matcher = WaiverMatcher([waiver])
    result = matcher.is_waived(message)

    assert result == waiver

def test_no_match_returns_none():
    waiver = Waiver(type="id", pattern="Vivado 12-9999", reason="test", author="test", date="2026-01-18")
    message = ParsedMessage(1, "WARNING: [Vivado 12-3523] different", "different", message_id="Vivado 12-3523")

    matcher = WaiverMatcher([waiver])
    result = matcher.is_waived(message)

    assert result is None
```

---

### Task 6.3: Waiver Generation

**Objective:** Generate waiver file from current log messages.

**Deliverables:**
- CLI option: `--generate-waivers`
- Output valid waiver TOML to stdout
- Include message metadata for review

**Success Criteria:**
- [ ] Generates valid TOML waiver file
- [ ] Includes all unwaived errors/warnings
- [ ] User can redirect to file: `sawmill log --generate-waivers > waivers.toml`

**Tests:**
```python
# tests/test_waiver_generation.py
import tomli
from click.testing import CliRunner
from sawmill.cli import cli

def test_generate_waivers(tmp_path):
    log_file = tmp_path / "vivado.log"
    log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] error message\nWARNING: [Test 2-1] warning\n")

    runner = CliRunner()
    result = runner.invoke(cli, [str(log_file), '--plugin', 'vivado', '--generate-waivers'])

    assert result.exit_code == 0
    assert "[[waiver]]" in result.output
    assert "Test 1-1" in result.output or "Test 2-1" in result.output

    # Output should be valid TOML
    parsed = tomli.loads(result.output)
    assert 'waiver' in parsed
```

---

## Stage 7: CI Mode

### Task 7.1: Exit Code Logic

**Objective:** Implement CI mode with pass/fail exit codes.

**Deliverables:**
- CLI option: `--ci` to enable CI mode
- Exit 0 if no errors/critical warnings
- Exit 1 if errors or critical warnings present
- `--strict` to also fail on regular warnings

**Success Criteria:**
- [ ] `sawmill --ci log` exits 0 on clean log
- [ ] `sawmill --ci log` exits 1 on errors
- [ ] `sawmill --ci --strict log` exits 1 on warnings

**Tests:**
```python
# tests/test_ci_mode.py
from click.testing import CliRunner
from sawmill.cli import cli

def test_ci_pass_on_clean_log(tmp_path):
    log_file = tmp_path / "clean.log"
    log_file.write_text("# Vivado v2025.2\nINFO: [Info 1-1] all good\n")

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

    assert result.exit_code == 0

def test_ci_fail_on_error(tmp_path):
    log_file = tmp_path / "errors.log"
    log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] something failed\n")

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

    assert result.exit_code == 1

def test_ci_fail_on_critical_warning(tmp_path):
    log_file = tmp_path / "critical.log"
    log_file.write_text("# Vivado v2025.2\nCRITICAL WARNING: [Test 1-1] important\n")

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', str(log_file)])

    assert result.exit_code == 1

def test_ci_strict_fails_on_warning(tmp_path):
    log_file = tmp_path / "warnings.log"
    log_file.write_text("# Vivado v2025.2\nWARNING: [Test 1-1] minor issue\n")

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', '--strict', '--plugin', 'vivado', str(log_file)])

    assert result.exit_code == 1
```

---

### Task 7.2: Waiver Integration in CI

**Objective:** Apply waivers in CI mode to ignore accepted issues.

**Deliverables:**
- CLI option: `--waivers <file>` to load waiver file
- Waived messages don't count toward failure
- `--show-waived` to display what was waived
- `--report-unused` to find stale waivers

**Success Criteria:**
- [ ] Waived errors don't cause CI failure
- [ ] `--show-waived` lists waived messages
- [ ] `--report-unused` identifies waivers that didn't match anything

**Tests:**
```python
# tests/test_ci_waivers.py
from click.testing import CliRunner
from sawmill.cli import cli

def test_ci_pass_with_waiver(tmp_path):
    log_file = tmp_path / "errors.log"
    log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] known issue\n")

    waiver_file = tmp_path / "waivers.toml"
    waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Known issue"
author = "test"
date = "2026-01-18"
''')

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', '--waivers', str(waiver_file), str(log_file)])

    assert result.exit_code == 0

def test_show_waived(tmp_path):
    log_file = tmp_path / "errors.log"
    log_file.write_text("# Vivado v2025.2\nERROR: [Test 1-1] known issue\n")

    waiver_file = tmp_path / "waivers.toml"
    waiver_file.write_text('''
[[waiver]]
type = "id"
pattern = "Test 1-1"
reason = "Known issue"
author = "test"
date = "2026-01-18"
''')

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', '--waivers', str(waiver_file), '--show-waived', str(log_file)])

    assert "waived" in result.output.lower() or "Test 1-1" in result.output
```

---

### Task 7.3: CI Summary Report

**Objective:** Generate structured summary report for CI systems.

**Deliverables:**
- CLI option: `--report <file>` to write JSON report
- Include: counts, waived items, unwaived issues

**Success Criteria:**
- [ ] Generates valid JSON report
- [ ] Includes error/warning counts
- [ ] Includes list of unwaived issues

**Tests:**
```python
# tests/test_ci_report.py
import json
from click.testing import CliRunner
from sawmill.cli import cli

def test_ci_report_generation(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text("# Vivado v2025.2\nERROR: [E1 1-1] e1\nWARNING: [W1 2-1] w1\nWARNING: [W2 2-2] w2\nINFO: [I1 3-1] i1\n")

    report_file = tmp_path / "report.json"

    runner = CliRunner()
    result = runner.invoke(cli, ['--ci', '--plugin', 'vivado', '--report', str(report_file), str(log_file)])

    assert report_file.exists()

    report = json.loads(report_file.read_text())

    assert 'summary' in report
    assert report['exit_code'] == 1  # Has error
```

---

## Stage 8: TUI (Deferred - Human-Guided)

> **Note:** This stage requires iterative human feedback for UX decisions.
> It should NOT be attempted by the automated ralph loop.
> Develop interactively with user testing.

### Task 8.1: Basic TUI Shell

**Objective:** Create minimal Textual application with log viewing.

**Approach:** Develop iteratively with human feedback on:
- Layout decisions
- Color schemes
- Keyboard shortcuts
- Scroll behavior

---

### Task 8.2: Interactive Filtering

**Objective:** Add filter controls to TUI.

**Approach:** Develop iteratively with human feedback on:
- Filter panel placement
- Toggle UX
- Real-time feedback

---

### Task 8.3: Waiver Management UI

**Objective:** Allow selecting and generating waivers from TUI.

**Approach:** Develop iteratively with human feedback on:
- Selection mechanism
- Preview display
- Export workflow

---

## Summary: Task Checklist

### Stage 1: Project Setup (Ralph Loop)
- [ ] Task 1.0: Test Infrastructure
- [ ] Task 1.1: Project Scaffolding
- [ ] Task 1.2: Data Model Interfaces

### Stage 2: Plugin System (Ralph Loop)
- [ ] Task 2.1: Plugin Hook Specification
- [ ] Task 2.2: Plugin Manager with Entry Point Discovery
- [ ] Task 2.3: Auto-Detection and Plugin Selection
- [ ] Task 2.4: Built-in Vivado Plugin
- [ ] Task 2.5: Plugin Discovery CLI

### Stage 3: Filter Engine (Ralph Loop)
- [ ] Task 3.1: Basic Regex Filter Engine
- [ ] Task 3.2: Filter Statistics

### Stage 4: CLI Streaming Interface (Ralph Loop)
- [ ] Task 4.1: Basic CLI with Stdout Output
- [ ] Task 4.2: Output Formats
- [ ] Task 4.3: Message ID Filtering
- [ ] Task 4.4: CLI Integration Tests

### Stage 5: Configuration System (Ralph Loop)
- [ ] Task 5.1: TOML Configuration Loader
- [ ] Task 5.2: Configuration Discovery and Merging

### Stage 6: Waiver System (Ralph Loop)
- [ ] Task 6.1: Waiver Data Model and Parser
- [ ] Task 6.2: Waiver Matching Engine
- [ ] Task 6.3: Waiver Generation

### Stage 7: CI Mode (Ralph Loop)
- [ ] Task 7.1: Exit Code Logic
- [ ] Task 7.2: Waiver Integration in CI
- [ ] Task 7.3: CI Summary Report

### Stage 8: TUI (Human-Guided - NOT for Ralph Loop)
- [ ] Task 8.1: Basic TUI Shell
- [ ] Task 8.2: Interactive Filtering
- [ ] Task 8.3: Waiver Management UI

---

**Total: 22 tasks across 8 stages**
- **19 tasks** suitable for ralph loop (Stages 1-7)
- **3 tasks** require human guidance (Stage 8)

Each task is designed to be:
1. **Self-contained**: Can be implemented independently
2. **Testable**: Has specific tests that must pass
3. **Context-friendly**: Small enough for a single session
4. **Incremental**: Builds on previous tasks without requiring future ones
