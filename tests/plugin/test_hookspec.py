"""Tests for the plugin hook specification.

Tests verify that:
- SawmillHookSpec defines all required hooks
- hookimpl decorator is available for plugins
- SawmillPlugin base class provides sensible defaults
"""

from pathlib import Path

from sawmill.plugin import SawmillPlugin, hookimpl, SawmillHookSpec


def test_hookspec_defines_required_hooks():
    """SawmillHookSpec should define all required hooks."""
    spec = SawmillHookSpec()
    assert hasattr(spec, "can_handle")
    assert hasattr(spec, "load_and_parse")
    assert hasattr(spec, "get_filters")


def test_hookspec_defines_file_reference_hook():
    """SawmillHookSpec should define extract_file_reference hook."""
    spec = SawmillHookSpec()
    assert hasattr(spec, "extract_file_reference")


def test_base_plugin_has_defaults():
    """SawmillPlugin should provide default implementations."""

    class TestPlugin(SawmillPlugin):
        name = "test"

    plugin = TestPlugin()
    # Default implementations should return empty/None (opt-out)
    assert plugin.can_handle(Path("test.log")) == 0.0
    assert plugin.load_and_parse(Path("test.log")) == []
    assert plugin.get_filters() == []


def test_base_plugin_extract_file_reference_default():
    """SawmillPlugin.extract_file_reference should return None by default."""

    class TestPlugin(SawmillPlugin):
        name = "test"

    plugin = TestPlugin()
    assert plugin.extract_file_reference("some content [file.v:123]") is None


def test_hookimpl_decorator_available():
    """hookimpl decorator should be importable and usable."""
    # This test verifies that hookimpl can be used as a decorator
    class TestPlugin(SawmillPlugin):
        name = "test"

        @hookimpl
        def can_handle(self, path):
            return 0.5

    plugin = TestPlugin()
    assert plugin.can_handle(Path("test.log")) == 0.5


def test_plugin_can_override_hooks():
    """Subclasses should be able to override hook implementations."""
    from sawmill.models.message import Message
    from sawmill.models.filter_def import FilterDefinition
    from sawmill.models.message import FileRef

    class CustomPlugin(SawmillPlugin):
        name = "custom"
        version = "1.0.0"

        @hookimpl
        def can_handle(self, path):
            return 0.9 if "custom" in str(path) else 0.0

        @hookimpl
        def load_and_parse(self, path):
            return [
                Message(
                    start_line=1,
                    end_line=1,
                    raw_text="Test message",
                    content="Test message",
                )
            ]

        @hookimpl
        def get_filters(self):
            return [
                FilterDefinition(
                    id="test",
                    name="Test Filter",
                    pattern=r"test",
                    enabled=True,
                )
            ]

        @hookimpl
        def extract_file_reference(self, content):
            if "[" in content and "]" in content:
                return FileRef(path="/test/file.v", line=42)
            return None

    plugin = CustomPlugin()

    # Test can_handle
    assert plugin.can_handle(Path("custom.log")) == 0.9
    assert plugin.can_handle(Path("other.log")) == 0.0

    # Test load_and_parse
    messages = plugin.load_and_parse(Path("test.log"))
    assert len(messages) == 1
    assert messages[0].content == "Test message"

    # Test get_filters
    filters = plugin.get_filters()
    assert len(filters) == 1
    assert filters[0].id == "test"

    # Test extract_file_reference
    ref = plugin.extract_file_reference("message [file.v:42]")
    assert ref is not None
    assert ref.path == "/test/file.v"
    assert ref.line == 42

    ref_none = plugin.extract_file_reference("message without reference")
    assert ref_none is None


def test_plugin_attributes():
    """Plugin should have name, version, and description attributes."""

    class FullPlugin(SawmillPlugin):
        name = "full-plugin"
        version = "2.1.0"
        description = "A fully configured plugin"

    plugin = FullPlugin()
    assert plugin.name == "full-plugin"
    assert plugin.version == "2.1.0"
    assert plugin.description == "A fully configured plugin"


def test_base_plugin_default_attributes():
    """Base plugin should have default attribute values."""
    plugin = SawmillPlugin()
    assert plugin.name == "base"
    assert plugin.version == "0.0.0"
    assert plugin.description == ""
