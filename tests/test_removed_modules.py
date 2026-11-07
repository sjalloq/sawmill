"""Tests asserting the old waiver/suppression modules have been removed."""

import importlib.util

import pytest


@pytest.mark.parametrize(
    "name",
    [
        "sawmill.core.waiver",
        "sawmill.core.suppress",
        "sawmill.models.waiver",
        "sawmill.utils.dirs",
        "sawmill.tui.session",
        "sawmill.cli.processing",
        "sawmill.cli.reporting",
        "sawmill.cli.formatting",
    ],
)
def test_module_removed(name: str) -> None:
    """The module no longer exists."""
    assert importlib.util.find_spec(name) is None


def test_waiver_loader_not_exported() -> None:
    """WaiverLoader is no longer exported from sawmill.core."""
    with pytest.raises(ImportError):
        from sawmill.core import WaiverLoader  # noqa: F401
