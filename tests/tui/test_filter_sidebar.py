"""Tests for the filter sidebar widget."""

import pytest

from sawmill.tui.widgets.filter_sidebar import (
    FilterSidebar,
    FilterChanged,
    SeverityCheckbox,
)


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
            show_info=True,
            show_warning=True,
            show_error=False,
            show_critical=False,
            pattern="test",
        )
        assert msg.show_info is True
        assert msg.show_warning is True
        assert msg.show_error is False
        assert msg.show_critical is False
        assert msg.pattern == "test"


class TestFilterSidebar:
    """Tests for FilterSidebar widget."""

    def test_init(self):
        """Test widget initialization."""
        sidebar = FilterSidebar()
        assert sidebar.show_info is True
        assert sidebar.show_warning is True
        assert sidebar.show_error is True
        assert sidebar.show_critical is True
        assert sidebar.pattern == ""

    def test_get_filter_state(self):
        """Test getting filter state as dictionary."""
        sidebar = FilterSidebar()
        sidebar.show_info = False
        sidebar.pattern = "error"

        state = sidebar.get_filter_state()
        assert state["show_info"] is False
        assert state["show_warning"] is True
        assert state["show_error"] is True
        assert state["show_critical"] is True
        assert state["pattern"] == "error"

    def test_initial_filter_state(self):
        """Test initial filter state shows all."""
        sidebar = FilterSidebar()
        state = sidebar.get_filter_state()

        # All severity levels should be enabled by default
        assert state["show_info"] is True
        assert state["show_warning"] is True
        assert state["show_error"] is True
        assert state["show_critical"] is True
        assert state["pattern"] == ""


class TestFilterSidebarImports:
    """Tests for widget imports."""

    def test_import_from_widgets_package(self):
        """Test widgets can be imported from the widgets package."""
        from sawmill.tui.widgets import FilterSidebar, FilterChanged, SeverityCheckbox

        assert FilterSidebar is not None
        assert FilterChanged is not None
        assert SeverityCheckbox is not None
