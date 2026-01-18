"""Tests for FilterDefinition model."""

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


def test_filter_defaults():
    """Test default values for optional fields."""
    f = FilterDefinition(
        id="minimal",
        name="Minimal",
        pattern="test"
    )
    assert f.enabled is True
    assert f.source is None
    assert f.description is None


def test_filter_with_description():
    """Filter can have a description."""
    f = FilterDefinition(
        id="timing",
        name="Timing Errors",
        pattern=r"timing slack.*negative",
        enabled=True,
        description="Matches timing violations with negative slack"
    )
    assert f.description == "Matches timing violations with negative slack"


def test_filter_equality():
    """Filters with same values should be equal."""
    f1 = FilterDefinition(id="a", name="A", pattern="test", enabled=True)
    f2 = FilterDefinition(id="a", name="A", pattern="test", enabled=True)
    assert f1 == f2


def test_filter_inequality():
    """Filters with different values should not be equal."""
    f1 = FilterDefinition(id="a", name="A", pattern="test1", enabled=True)
    f2 = FilterDefinition(id="a", name="A", pattern="test2", enabled=True)
    assert f1 != f2


def test_complex_regex_accepted():
    """Complex but valid regex patterns should be accepted."""
    f = FilterDefinition(
        id="complex",
        name="Complex",
        pattern=r"^(?:ERROR|WARNING):\s+\[(\w+)\s+(\d+-\d+)\]\s+(.*)$",
        enabled=True
    )
    assert f.pattern == r"^(?:ERROR|WARNING):\s+\[(\w+)\s+(\d+-\d+)\]\s+(.*)$"


def test_invalid_regex_various():
    """Various invalid regex patterns should be rejected."""
    invalid_patterns = [
        r"[",            # Unclosed bracket
        r"(",            # Unclosed group
        r"*abc",         # Nothing to repeat
        r"+abc",         # Nothing to repeat
        r"(?P<",         # Incomplete named group
    ]
    for pattern in invalid_patterns:
        with pytest.raises(ValueError):
            FilterDefinition(
                id="bad",
                name="Bad",
                pattern=pattern,
                enabled=True
            )
