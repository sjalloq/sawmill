"""Tests for the custom footer widget."""

import pytest

from sawmill.tui.widgets.footer import SawmillFooter


class TestSawmillFooter:
    """Tests for the SawmillFooter widget."""

    def test_init_no_bindings(self):
        """Test footer can be initialized without bindings."""
        footer = SawmillFooter()
        assert footer._bindings == []

    def test_init_with_bindings(self):
        """Test footer initializes with binding list."""
        bindings = [("q", "Quit"), ("/", "Search")]
        footer = SawmillFooter(bindings=bindings)
        assert footer._bindings == bindings

    def test_import_from_widgets_package(self):
        """Test footer can be imported from widgets package."""
        from sawmill.tui.widgets import SawmillFooter
        assert SawmillFooter is not None

    def test_import_from_module(self):
        """Test footer can be imported from module."""
        from sawmill.tui.widgets.footer import SawmillFooter
        assert SawmillFooter is not None
