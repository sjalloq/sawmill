"""Tests for the FilterModal widget."""

import pytest

from sawmill.models.plugin_api import SeverityLevel
from sawmill.tui.widgets.filter_modal import FilterModal


@pytest.fixture
def severity_levels():
    """Standard Vivado-like severity levels for tests."""
    return [
        SeverityLevel(id="error", name="Error", level=3, style="red bold"),
        SeverityLevel(id="critical_warning", name="Critical Warning", level=2, style="red"),
        SeverityLevel(id="warning", name="Warning", level=1, style="yellow"),
        SeverityLevel(id="info", name="Info", level=0, style="cyan"),
    ]


@pytest.fixture
def custom_severity_levels():
    """Non-Vivado severity scheme."""
    return [
        SeverityLevel(id="fatal", name="Fatal", level=3, style="red bold"),
        SeverityLevel(id="major", name="Major", level=2, style="red"),
        SeverityLevel(id="minor", name="Minor", level=1, style="yellow"),
        SeverityLevel(id="note", name="Note", level=0, style="dim"),
    ]


class TestFilterModalInit:
    """Tests for FilterModal initialization."""

    def test_init_basic(self, severity_levels):
        """Test basic initialization."""
        modal = FilterModal(severity_levels)
        assert modal._severity_levels == severity_levels
        assert modal._current_filter == {}

    def test_init_with_current_filter(self, severity_levels):
        """Test initialization with pre-populated filter."""
        current = {
            "severity_filter": {"error": True, "warning": False},
            "pattern": "test.*pattern",
        }
        modal = FilterModal(severity_levels, current_filter=current)
        assert modal._current_filter == current

    def test_init_custom_severity_scheme(self, custom_severity_levels):
        """Test initialization with non-Vivado severity scheme."""
        modal = FilterModal(custom_severity_levels)
        assert len(modal._severity_levels) == 4
        ids = [l.id for l in modal._severity_levels]
        assert "fatal" in ids
        assert "major" in ids


class TestFilterModalImports:
    """Tests for FilterModal imports."""

    def test_import_from_widgets_package(self):
        """Test FilterModal can be imported from widgets package."""
        from sawmill.tui.widgets import FilterModal
        assert FilterModal is not None

    def test_import_from_module(self):
        """Test FilterModal can be imported directly."""
        from sawmill.tui.widgets.filter_modal import FilterModal
        assert FilterModal is not None


class TestFilterModalCancelAction:
    """Tests for the cancel action."""

    def test_action_cancel_method_exists(self, severity_levels):
        """Test that action_cancel method exists."""
        modal = FilterModal(severity_levels)
        assert hasattr(modal, "action_cancel")
        assert callable(modal.action_cancel)


class TestFilterModalApply:
    """Tests for the _apply method."""

    def test_apply_method_exists(self, severity_levels):
        """Test that _apply method exists."""
        modal = FilterModal(severity_levels)
        assert hasattr(modal, "_apply")
        assert callable(modal._apply)
