"""Tests for plugin auto-detection functionality."""

from pathlib import Path

import pytest

from sawmill.core.plugin import NoPluginFoundError, PluginConflictError, PluginManager
from sawmill.plugin import SawmillPlugin, hookimpl


def test_auto_detect_selects_highest_confidence():
    """Auto-detect should select the plugin with highest confidence score."""
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
    """If no plugin has confidence >= 0.5, raise NoPluginFoundError."""
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
    """If multiple plugins both return >= 0.5, raise PluginConflictError."""
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


def test_auto_detect_with_no_plugins():
    """With no plugins registered, should raise NoPluginFoundError."""
    manager = PluginManager()

    with pytest.raises(NoPluginFoundError) as exc:
        manager.auto_detect(Path("test.log"))
    assert "no plugin" in str(exc.value).lower()


def test_auto_detect_single_plugin_high_confidence():
    """Single plugin with high confidence should be selected."""
    manager = PluginManager()

    class OnlyPlugin(SawmillPlugin):
        name = "only"

        @hookimpl
        def can_handle(self, path):
            return 0.85

    manager.register(OnlyPlugin())

    selected = manager.auto_detect(Path("test.log"))
    assert selected == "only"


def test_auto_detect_single_plugin_low_confidence():
    """Single plugin with low confidence should raise NoPluginFoundError."""
    manager = PluginManager()

    class LowConfPlugin(SawmillPlugin):
        name = "lowconf"

        @hookimpl
        def can_handle(self, path):
            return 0.49

    manager.register(LowConfPlugin())

    with pytest.raises(NoPluginFoundError):
        manager.auto_detect(Path("test.log"))


def test_auto_detect_boundary_confidence():
    """Plugin with exactly 0.5 confidence should be selected."""
    manager = PluginManager()

    class BoundaryPlugin(SawmillPlugin):
        name = "boundary"

        @hookimpl
        def can_handle(self, path):
            return 0.5

    manager.register(BoundaryPlugin())

    selected = manager.auto_detect(Path("test.log"))
    assert selected == "boundary"


def test_auto_detect_mixed_confidence():
    """Should select high confidence plugin when mixed with low confidence ones."""
    manager = PluginManager()

    class LowPlugin1(SawmillPlugin):
        name = "low1"

        @hookimpl
        def can_handle(self, path):
            return 0.1

    class LowPlugin2(SawmillPlugin):
        name = "low2"

        @hookimpl
        def can_handle(self, path):
            return 0.3

    class HighPlugin(SawmillPlugin):
        name = "winner"

        @hookimpl
        def can_handle(self, path):
            return 0.7

    manager.register(LowPlugin1())
    manager.register(LowPlugin2())
    manager.register(HighPlugin())

    selected = manager.auto_detect(Path("test.log"))
    assert selected == "winner"


def test_auto_detect_error_message_shows_best_match():
    """When no plugin has high confidence, error should show best match."""
    manager = PluginManager()

    class Plugin1(SawmillPlugin):
        name = "plugin1"

        @hookimpl
        def can_handle(self, path):
            return 0.2

    class Plugin2(SawmillPlugin):
        name = "plugin2"

        @hookimpl
        def can_handle(self, path):
            return 0.4

    manager.register(Plugin1())
    manager.register(Plugin2())

    with pytest.raises(NoPluginFoundError) as exc:
        manager.auto_detect(Path("test.log"))
    # Should mention the best match (plugin2 with 0.4)
    assert "plugin2" in str(exc.value)


def test_auto_detect_conflict_error_shows_conflicting_plugins():
    """Conflict error should list all conflicting plugins."""
    manager = PluginManager()

    class PluginX(SawmillPlugin):
        name = "plugin_x"

        @hookimpl
        def can_handle(self, path):
            return 0.9

    class PluginY(SawmillPlugin):
        name = "plugin_y"

        @hookimpl
        def can_handle(self, path):
            return 0.85

    manager.register(PluginX())
    manager.register(PluginY())

    with pytest.raises(PluginConflictError) as exc:
        manager.auto_detect(Path("test.log"))
    error_msg = str(exc.value)
    # Both conflicting plugins should be mentioned
    assert "plugin_x" in error_msg
    assert "plugin_y" in error_msg


def test_auto_detect_handles_plugin_exception():
    """Plugin that raises exception should be skipped."""
    manager = PluginManager()

    class FailingPlugin(SawmillPlugin):
        name = "failing"

        @hookimpl
        def can_handle(self, path):
            raise RuntimeError("Plugin error")

    class WorkingPlugin(SawmillPlugin):
        name = "working"

        @hookimpl
        def can_handle(self, path):
            return 0.8

    manager.register(FailingPlugin())
    manager.register(WorkingPlugin())

    # Should select working plugin and skip failing one
    selected = manager.auto_detect(Path("test.log"))
    assert selected == "working"


def test_auto_detect_with_path_specific_confidence(tmp_path):
    """Plugins should be able to give different confidence based on path."""
    manager = PluginManager()

    class VivadoLikePlugin(SawmillPlugin):
        name = "vivado_like"

        @hookimpl
        def can_handle(self, path):
            if "vivado" in str(path).lower():
                return 0.9
            return 0.1

    class GenericPlugin(SawmillPlugin):
        name = "generic"

        @hookimpl
        def can_handle(self, path):
            return 0.4

    manager.register(VivadoLikePlugin())
    manager.register(GenericPlugin())

    # Vivado log should select vivado_like plugin
    vivado_log = tmp_path / "vivado.log"
    vivado_log.write_text("some content")
    selected = manager.auto_detect(vivado_log)
    assert selected == "vivado_like"

    # Non-vivado log should fail (no high confidence)
    other_log = tmp_path / "other.log"
    other_log.write_text("some content")
    with pytest.raises(NoPluginFoundError):
        manager.auto_detect(other_log)
