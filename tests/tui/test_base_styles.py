"""Tests for modal widget styling — live Textual tests."""

from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from sawmill.tui.widgets.waive_modal import WaiveModal


class ModalTestApp(App):
    """Minimal app for testing modals."""

    def compose(self) -> ComposeResult:
        yield Static("test")


# --- WaiveModal (Task 3) ---


@pytest.fixture
async def waive_modal():
    """Push a WaiveModal and yield (app, pilot) for assertions."""
    app = ModalTestApp()
    async with app.run_test() as pilot:
        await app.push_screen(
            WaiveModal(
                message_id="TEST-001",
                severity="error",
                content="test content",
                log_rel_path="a.log",
                target_files=[Path("t.toml")],
                plugin_files=[],
                author="tester",
            )
        )
        await pilot.pause()
        yield app, pilot


class TestWaiveModalClasses:
    """Container, title, and footer carry the shared modal CSS classes."""

    async def test_container_has_modal_container_class(self, waive_modal):
        app, _ = waive_modal
        container = app.screen.query_one("#waive-modal-container")
        assert "modal-container" in container.classes

    async def test_title_has_modal_title_class(self, waive_modal):
        app, _ = waive_modal
        title = app.screen.query_one("#waive-modal-title")
        assert "modal-title" in title.classes

    async def test_footer_has_modal_footer_class(self, waive_modal):
        app, _ = waive_modal
        footer = app.screen.query_one("#waive-modal-footer")
        assert "modal-footer" in footer.classes

    async def test_no_thick_border_in_css(self):
        assert "thick" not in WaiveModal.DEFAULT_CSS

    async def test_no_surface_background_in_css(self):
        assert "$surface" not in WaiveModal.DEFAULT_CSS


class TestWaiveModalDismiss:
    """Escape cancels, Enter with valid fields confirms."""

    async def test_escape_dismisses_with_none(self):
        result = []
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await app.push_screen(
                WaiveModal(
                    message_id="X-1",
                    severity="error",
                    content="msg",
                    log_rel_path="a.log",
                    target_files=[Path("t.toml")],
                    plugin_files=[],
                    author="me",
                ),
                callback=result.append,
            )
            await pilot.pause()
            await pilot.press("escape")
        assert result == [None]


# --- Screenshot binding on modals ---


class TestModalScreenshotBinding:
    """The waive modal exposes an F12 screenshot binding."""

    async def test_waive_modal_has_f12_binding(self):
        keys = [b[0] for b in WaiveModal.BINDINGS]
        assert "f12" in keys
