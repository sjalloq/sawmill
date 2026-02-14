"""Tests for modal widget styling — live Textual tests."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from sawmill.tui.widgets.quit_modal import QuitConfirmModal
from sawmill.tui.widgets.waive_modal import WaiveModal


class ModalTestApp(App):
    """Minimal app for testing modals."""

    def compose(self) -> ComposeResult:
        yield Static("test")


@pytest.fixture
async def quit_modal():
    """Push a QuitConfirmModal and yield (app, pilot) for assertions."""
    app = ModalTestApp()
    async with app.run_test() as pilot:
        await app.push_screen(QuitConfirmModal(suppression_count=2, waiver_count=1))
        await pilot.pause()
        yield app, pilot


class TestQuitConfirmModalClasses:
    """Container, title, and footer carry the shared modal CSS classes."""

    async def test_container_has_modal_container_class(self, quit_modal):
        app, _ = quit_modal
        container = app.screen.query_one("#quit-modal-container")
        assert "modal-container" in container.classes

    async def test_title_has_modal_title_class(self, quit_modal):
        app, _ = quit_modal
        title = app.screen.query_one("#quit-modal-title")
        assert "modal-title" in title.classes

    async def test_footer_has_modal_footer_class(self, quit_modal):
        app, _ = quit_modal
        options = app.screen.query_one("#quit-modal-options")
        assert "modal-footer" in options.classes


class TestQuitConfirmModalDismiss:
    """Key bindings dismiss with the correct values."""

    async def test_escape_dismisses_with_none(self):
        result = []
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await app.push_screen(
                QuitConfirmModal(suppression_count=1),
                callback=result.append,
            )
            await pilot.pause()
            await pilot.press("escape")
        assert result == [None]

    async def test_enter_dismisses_with_save_quit(self):
        result = []
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await app.push_screen(
                QuitConfirmModal(suppression_count=1),
                callback=result.append,
            )
            await pilot.pause()
            await pilot.press("enter")
        assert result == ["save_quit"]

    async def test_q_dismisses_with_discard_quit(self):
        result = []
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await app.push_screen(
                QuitConfirmModal(suppression_count=1),
                callback=result.append,
            )
            await pilot.pause()
            await pilot.press("q")
        assert result == ["discard_quit"]


class TestQuitConfirmModalContent:
    """Modal displays the correct counts."""

    async def test_suppression_count_displayed(self):
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await app.push_screen(QuitConfirmModal(suppression_count=3))
            await pilot.pause()
            items = app.screen.query(".quit-item")
            texts = [w.content for w in items]
            assert any("3 suppression rules" in t for t in texts)

    async def test_waiver_count_displayed(self):
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await app.push_screen(QuitConfirmModal(waiver_count=1))
            await pilot.pause()
            items = app.screen.query(".quit-item")
            texts = [w.content for w in items]
            assert any("1 waiver entry" in t for t in texts)

    async def test_both_counts_displayed(self, quit_modal):
        app, _ = quit_modal
        items = app.screen.query(".quit-item")
        texts = [w.content for w in items]
        assert any("2 suppression rules" in t for t in texts)
        assert any("1 waiver entry" in t for t in texts)


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
                    author="me",
                ),
                callback=result.append,
            )
            await pilot.pause()
            await pilot.press("escape")
        assert result == [None]


# --- Screenshot binding on modals ---


class TestModalScreenshotBinding:
    """Both modals expose an F12 screenshot binding."""

    async def test_quit_modal_has_f12_binding(self):
        keys = [b[0] for b in QuitConfirmModal.BINDINGS]
        assert "f12" in keys

    async def test_waive_modal_has_f12_binding(self):
        keys = [b[0] for b in WaiveModal.BINDINGS]
        assert "f12" in keys
