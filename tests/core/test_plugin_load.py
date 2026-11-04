"""Tests for the load_messages compatibility helper."""

from pathlib import Path

from sawmill.core.plugin import load_messages
from sawmill.models.message import Message

MSGS = [Message(start_line=i, end_line=i, raw_text=f"m{i}", content=f"m{i}") for i in (1, 2)]


class ListPlugin:
    def load_and_parse(self, path):
        return list(MSGS)


class GenPlugin:
    def load_and_parse(self, path):
        yield from MSGS


def test_list_and_generator_plugins_yield_same_messages():
    a = load_messages(ListPlugin(), Path("x.log"))
    b = load_messages(GenPlugin(), Path("x.log"))
    assert iter(a) is a and iter(b) is b
    assert list(a) == list(b) == MSGS
