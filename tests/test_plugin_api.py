"""Tests for the extensible plugin API (severity levels, grouping fields, metadata)."""

import pytest
from click.testing import CliRunner

from sawmill.__main__ import cli
from sawmill.models.message import Message, FileRef
from sawmill.models.plugin_api import (
    SeverityLevel,
    GroupingField,
    DEFAULT_SEVERITY_LEVELS,
    DEFAULT_GROUPING_FIELDS,
    severity_levels_from_dicts,
    grouping_fields_from_dicts,
)
from sawmill.core.aggregation import Aggregator, make_severity_sort_key
from sawmill.plugins.vivado import VivadoPlugin


class TestSeverityLevel:
    """Tests for SeverityLevel model."""

    def test_basic_init(self):
        """Test basic initialization."""
        level = SeverityLevel(id="error", name="Error", level=2, style="red")
        assert level.id == "error"
        assert level.name == "Error"
        assert level.level == 2
        assert level.style == "red"

    def test_defaults(self):
        """Test default values."""
        level = SeverityLevel(id="test", name="Test")
        assert level.level == 0
        assert level.style == ""

    def test_frozen(self):
        """Test that SeverityLevel is immutable."""
        level = SeverityLevel(id="error", name="Error")
        with pytest.raises(Exception):  # Pydantic ValidationError
            level.id = "warning"


class TestGroupingField:
    """Tests for GroupingField model."""

    def test_basic_init(self):
        """Test basic initialization."""
        field = GroupingField(
            id="hierarchy",
            name="Design Hierarchy",
            field_type="metadata",
            description="Group by RTL hierarchy",
        )
        assert field.id == "hierarchy"
        assert field.name == "Design Hierarchy"
        assert field.field_type == "metadata"
        assert field.description == "Group by RTL hierarchy"

    def test_defaults(self):
        """Test default values."""
        field = GroupingField(id="test", name="Test")
        assert field.field_type == "builtin"
        assert field.description == ""
        assert field.sort_order is None

    def test_with_sort_order(self):
        """Test field with custom sort order."""
        field = GroupingField(
            id="severity",
            name="Severity",
            sort_order=["critical", "error", "warning", "info"],
        )
        assert field.sort_order == ["critical", "error", "warning", "info"]


class TestDefaultLevelsAndFields:
    """Tests for default severity levels and grouping fields."""

    def test_default_severity_levels(self):
        """Test default severity levels are defined correctly."""
        assert len(DEFAULT_SEVERITY_LEVELS) >= 4
        ids = [s.id for s in DEFAULT_SEVERITY_LEVELS]
        assert "error" in ids
        assert "warning" in ids
        assert "info" in ids

    def test_default_grouping_fields(self):
        """Test default grouping fields are defined correctly."""
        assert len(DEFAULT_GROUPING_FIELDS) >= 4
        ids = [f.id for f in DEFAULT_GROUPING_FIELDS]
        assert "severity" in ids
        assert "id" in ids
        assert "file" in ids
        assert "category" in ids


class TestConversionFunctions:
    """Tests for dict-to-model conversion functions."""

    def test_severity_levels_from_dicts(self):
        """Test converting dicts to SeverityLevel objects."""
        dicts = [
            {"id": "fatal", "name": "Fatal", "level": 3, "style": "red bold"},
            {"id": "error", "name": "Error", "level": 2, "style": "red"},
        ]
        levels = severity_levels_from_dicts(dicts)
        assert len(levels) == 2
        assert levels[0].id == "fatal"
        assert levels[1].id == "error"

    def test_grouping_fields_from_dicts(self):
        """Test converting dicts to GroupingField objects."""
        dicts = [
            {"id": "severity", "name": "Severity", "field_type": "builtin"},
            {"id": "hierarchy", "name": "Hierarchy", "field_type": "metadata"},
        ]
        fields = grouping_fields_from_dicts(dicts)
        assert len(fields) == 2
        assert fields[0].id == "severity"
        assert fields[1].field_type == "metadata"


class TestMessageMetadata:
    """Tests for Message.metadata field."""

    def test_message_has_metadata_field(self):
        """Test that Message has metadata field."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="test",
            content="test",
        )
        assert hasattr(msg, "metadata")
        assert isinstance(msg.metadata, dict)

    def test_message_with_metadata(self):
        """Test creating message with metadata."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="test",
            content="test",
            metadata={"hierarchy": "top/fifo", "phase": "synthesis"},
        )
        assert msg.metadata["hierarchy"] == "top/fifo"
        assert msg.metadata["phase"] == "synthesis"

    def test_get_field_value_builtin(self):
        """Test get_field_value for builtin fields."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="test",
            content="test",
            severity="error",
            message_id="E-001",
            category="timing",
        )
        assert msg.get_field_value("severity") == "error"
        assert msg.get_field_value("id") == "E-001"
        assert msg.get_field_value("message_id") == "E-001"
        assert msg.get_field_value("category") == "timing"

    def test_get_field_value_file_ref(self):
        """Test get_field_value for file_ref."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="test",
            content="test",
            file_ref=FileRef(path="/src/test.v", line=10),
        )
        assert msg.get_field_value("file") == "/src/test.v"

    def test_get_field_value_metadata(self):
        """Test get_field_value for metadata fields."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="test",
            content="test",
            metadata={"hierarchy": "top/fifo"},
        )
        assert msg.get_field_value("hierarchy") == "top/fifo"

    def test_get_field_value_none(self):
        """Test get_field_value returns None for missing fields."""
        msg = Message(
            start_line=1,
            end_line=1,
            raw_text="test",
            content="test",
        )
        assert msg.get_field_value("severity") is None
        assert msg.get_field_value("nonexistent") is None


class TestAggregatorWithPluginMetadata:
    """Tests for Aggregator with plugin-provided metadata."""

    def test_aggregator_with_severity_levels(self):
        """Test Aggregator uses custom severity levels."""
        custom_levels = [
            SeverityLevel(id="fatal", name="Fatal", level=3),
            SeverityLevel(id="error", name="Error", level=2),
            SeverityLevel(id="note", name="Note", level=0),
        ]
        aggregator = Aggregator(severity_levels=custom_levels)
        assert aggregator.severity_levels == custom_levels

    def test_aggregator_with_grouping_fields(self):
        """Test Aggregator with custom grouping fields."""
        custom_fields = [
            GroupingField(id="severity", name="Severity", field_type="builtin"),
            GroupingField(id="hierarchy", name="Hierarchy", field_type="metadata"),
        ]
        aggregator = Aggregator(grouping_fields=custom_fields)
        assert aggregator.get_available_groupings() == ["severity", "hierarchy"]

    def test_get_severity_style_from_plugin(self):
        """Test getting severity style from plugin-provided levels."""
        custom_levels = [
            SeverityLevel(id="fatal", name="Fatal", level=3, style="magenta bold"),
        ]
        aggregator = Aggregator(severity_levels=custom_levels)
        assert aggregator.get_severity_style("fatal") == "magenta bold"

    def test_get_severity_name_from_plugin(self):
        """Test getting severity name from plugin-provided levels."""
        custom_levels = [
            SeverityLevel(id="fatal", name="Fatal Error", level=3),
        ]
        aggregator = Aggregator(severity_levels=custom_levels)
        assert aggregator.get_severity_name("fatal") == "Fatal Error"

    def test_group_by_metadata_field(self):
        """Test grouping by a metadata field."""
        messages = [
            Message(
                start_line=1, end_line=1, raw_text="msg1", content="msg1",
                metadata={"hierarchy": "top/fifo"},
            ),
            Message(
                start_line=2, end_line=2, raw_text="msg2", content="msg2",
                metadata={"hierarchy": "top/ctrl"},
            ),
            Message(
                start_line=3, end_line=3, raw_text="msg3", content="msg3",
                metadata={"hierarchy": "top/fifo"},
            ),
        ]
        custom_fields = [
            GroupingField(id="hierarchy", name="Hierarchy", field_type="metadata"),
        ]
        aggregator = Aggregator(grouping_fields=custom_fields)
        groups = aggregator.group_by(messages, "hierarchy")

        assert "top/fifo" in groups
        assert "top/ctrl" in groups
        assert groups["top/fifo"].count == 2
        assert groups["top/ctrl"].count == 1


class TestMakeSeveritySortKey:
    """Tests for make_severity_sort_key function."""

    def test_default_severity_order(self):
        """Test default severity ordering."""
        sort_key = make_severity_sort_key()
        # More severe = lower sort key
        assert sort_key("critical") < sort_key("error")
        assert sort_key("error") < sort_key("warning")
        assert sort_key("warning") < sort_key("info")

    def test_custom_severity_order(self):
        """Test custom severity ordering from plugin."""
        custom_levels = [
            SeverityLevel(id="fatal", name="Fatal", level=4),
            SeverityLevel(id="error", name="Error", level=2),
            SeverityLevel(id="note", name="Note", level=0),
        ]
        sort_key = make_severity_sort_key(custom_levels)
        # Higher level = more severe = lower sort key
        assert sort_key("fatal") < sort_key("error")
        assert sort_key("error") < sort_key("note")

    def test_none_sorts_last(self):
        """Test None severity sorts last."""
        sort_key = make_severity_sort_key()
        assert sort_key(None) > sort_key("info")

    def test_unknown_severity(self):
        """Test unknown severity sorts before None."""
        sort_key = make_severity_sort_key()
        assert sort_key("unknown") < sort_key(None)
        assert sort_key("unknown") > sort_key("info")


class TestVivadoPluginNewHooks:
    """Tests for VivadoPlugin's new hook implementations."""

    @pytest.fixture
    def plugin(self):
        """Create a VivadoPlugin instance."""
        return VivadoPlugin()

    def test_get_severity_levels(self, plugin):
        """Test VivadoPlugin.get_severity_levels()."""
        levels = plugin.get_severity_levels()
        assert isinstance(levels, list)
        assert len(levels) >= 4

        # Check expected severity levels
        ids = [l["id"] for l in levels]
        assert "critical_warning" in ids
        assert "error" in ids
        assert "warning" in ids
        assert "info" in ids

    def test_get_grouping_fields(self, plugin):
        """Test VivadoPlugin.get_grouping_fields()."""
        fields = plugin.get_grouping_fields()
        assert isinstance(fields, list)
        assert len(fields) >= 4

        # Check expected grouping fields
        ids = [f["id"] for f in fields]
        assert "severity" in ids
        assert "id" in ids
        assert "category" in ids
        assert "file" in ids

    def test_severity_levels_have_required_fields(self, plugin):
        """Test severity levels have all required fields."""
        levels = plugin.get_severity_levels()
        for level in levels:
            assert "id" in level
            assert "name" in level
            assert "level" in level
            assert "style" in level

    def test_grouping_fields_have_required_fields(self, plugin):
        """Test grouping fields have all required fields."""
        fields = plugin.get_grouping_fields()
        for field in fields:
            assert "id" in field
            assert "name" in field
            assert "field_type" in field


class TestListGroupingsCLI:
    """Tests for --list-groupings CLI option."""

    @pytest.fixture
    def runner(self):
        """Create a CLI runner."""
        return CliRunner()

    def test_list_groupings_shows_fields(self, runner):
        """Test --list-groupings shows available fields."""
        result = runner.invoke(cli, ["--list-groupings", "--plugin", "vivado"])
        assert result.exit_code == 0
        assert "severity" in result.output.lower()
        assert "id" in result.output.lower()
        assert "file" in result.output.lower()

    def test_list_groupings_without_plugin_shows_defaults(self, runner):
        """Test --list-groupings without --plugin shows defaults."""
        result = runner.invoke(cli, ["--list-groupings"])
        assert result.exit_code == 0
        assert "severity" in result.output.lower()
        assert "No plugin specified" in result.output

    def test_list_groupings_shows_usage_hint(self, runner):
        """Test --list-groupings shows usage hint."""
        result = runner.invoke(cli, ["--list-groupings", "--plugin", "vivado"])
        assert result.exit_code == 0
        assert "--group-by" in result.output
