"""Tests for the filter sidebar widget."""

import pytest

from sawmill.models.plugin_api import SeverityLevel
from sawmill.tui.widgets.filter_sidebar import (
    FilterSidebar,
    FilterChanged,
    SeverityCheckbox,
)


@pytest.fixture
def severity_levels() -> list[SeverityLevel]:
    """Provide test severity levels."""
    return [
        SeverityLevel(id="error", name="Error", level=3, style="red bold"),
        SeverityLevel(id="critical_warning", name="Critical Warning", level=2, style="red"),
        SeverityLevel(id="warning", name="Warning", level=1, style="yellow"),
        SeverityLevel(id="info", name="Info", level=0, style="cyan"),
    ]


class TestSeverityCheckbox:
    """Tests for SeverityCheckbox widget."""

    def test_init(self):
        """Test initialization with severity."""
        checkbox = SeverityCheckbox("Error", severity="error", value=True)
        assert checkbox.severity == "error"
        assert checkbox.value is True

    def test_init_unchecked(self):
        """Test initialization with unchecked state."""
        checkbox = SeverityCheckbox("Warning", severity="warning", value=False)
        assert checkbox.severity == "warning"
        assert checkbox.value is False


class TestFilterChanged:
    """Tests for FilterChanged message."""

    def test_init(self):
        """Test message initialization."""
        msg = FilterChanged(
            severity_filter={
                "info": True,
                "warning": True,
                "error": False,
                "critical_warning": False,
            },
            pattern="test",
        )
        assert msg.severity_filter["info"] is True
        assert msg.severity_filter["warning"] is True
        assert msg.severity_filter["error"] is False
        assert msg.severity_filter["critical_warning"] is False
        assert msg.pattern == "test"

    def test_severity_filter_is_independent(self):
        """Test that severity_filter dict is independent of specific severity names."""
        # Test with custom severity names (non-Vivado)
        msg = FilterChanged(
            severity_filter={
                "fatal": False,
                "note": True,
                "debug": True,
            },
            pattern="",
        )
        assert msg.severity_filter["fatal"] is False
        assert msg.severity_filter["note"] is True
        assert msg.severity_filter["debug"] is True


class TestFilterSidebar:
    """Tests for FilterSidebar widget."""

    def test_requires_severity_levels(self):
        """Test that severity_levels is required."""
        with pytest.raises(ValueError, match="severity_levels is required"):
            FilterSidebar(severity_levels=[])

    def test_init(self, severity_levels):
        """Test widget initialization with severity levels."""
        sidebar = FilterSidebar(severity_levels=severity_levels)
        # All severities should be enabled by default
        assert sidebar._severity_filter["info"] is True
        assert sidebar._severity_filter["warning"] is True
        assert sidebar._severity_filter["critical_warning"] is True
        assert sidebar._severity_filter["error"] is True
        assert sidebar.pattern == ""

    def test_get_filter_state(self, severity_levels):
        """Test getting filter state as dictionary."""
        sidebar = FilterSidebar(severity_levels=severity_levels)
        sidebar._severity_filter["info"] = False
        sidebar.pattern = "error"

        state = sidebar.get_filter_state()
        assert state["severity_filter"]["info"] is False
        assert state["severity_filter"]["warning"] is True
        assert state["severity_filter"]["critical_warning"] is True
        assert state["severity_filter"]["error"] is True
        assert state["pattern"] == "error"

    def test_initial_filter_state(self, severity_levels):
        """Test initial filter state shows all severities."""
        sidebar = FilterSidebar(severity_levels=severity_levels)
        state = sidebar.get_filter_state()

        # All severity levels should be enabled by default
        for level in severity_levels:
            assert state["severity_filter"][level.id] is True
        assert state["pattern"] == ""

    def test_custom_severity_levels(self):
        """Test with custom (non-Vivado) severity levels."""
        custom_levels = [
            SeverityLevel(id="fatal", name="Fatal", level=4, style="red bold"),
            SeverityLevel(id="note", name="Note", level=0, style="blue"),
        ]
        sidebar = FilterSidebar(severity_levels=custom_levels)

        state = sidebar.get_filter_state()
        assert "fatal" in state["severity_filter"]
        assert "note" in state["severity_filter"]
        assert state["severity_filter"]["fatal"] is True
        assert state["severity_filter"]["note"] is True


class TestFilterSidebarImports:
    """Tests for widget imports."""

    def test_import_from_widgets_package(self):
        """Test widgets can be imported from the widgets package."""
        from sawmill.tui.widgets import FilterSidebar, FilterChanged, SeverityCheckbox

        assert FilterSidebar is not None
        assert FilterChanged is not None
        assert SeverityCheckbox is not None
