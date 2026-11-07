"""Tests for sawmill.core.severity.resolve_fail_on_level."""

from __future__ import annotations

import pytest

from sawmill.core.severity import get_severity_levels, resolve_fail_on_level
from sawmill.models.plugin_api import severity_levels_from_dicts


def _vivado_levels():  # type: ignore[no-untyped-def]
    from sawmill_plugin_vivado.plugin import VivadoPlugin

    return get_severity_levels(VivadoPlugin())


class TestResolveFailOnLevel:
    """Tests for resolve_fail_on_level() with various severity schemes."""

    def test_default_returns_second_lowest(self) -> None:
        # Vivado: info=0, warning=1, critical_warning=2, error=3
        assert resolve_fail_on_level(None, _vivado_levels()) == 1

    def test_default_with_custom_scheme(self) -> None:
        levels = severity_levels_from_dicts(
            [
                {"id": "fatal", "name": "Fatal", "level": 2, "style": "red"},
                {"id": "major", "name": "Major", "level": 1, "style": "yellow"},
                {"id": "note", "name": "Note", "level": 0, "style": "dim"},
            ]
        )
        assert resolve_fail_on_level(None, levels) == 1

    def test_default_with_single_level(self) -> None:
        levels = severity_levels_from_dicts(
            [{"id": "only", "name": "Only", "level": 1, "style": ""}]
        )
        assert resolve_fail_on_level(None, levels) == 1

    def test_explicit_fail_on(self) -> None:
        assert resolve_fail_on_level("error", _vivado_levels()) == 3

    def test_invalid_fail_on_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown severity"):
            resolve_fail_on_level("nonexistent", _vivado_levels())
