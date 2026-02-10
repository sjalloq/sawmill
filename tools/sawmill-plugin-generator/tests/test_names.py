"""Tests for name validation and derivation."""

import click
import pytest
from sawmill_plugin_generator.names import derive_names, validate_name


class TestValidateName:
    """Tests for validate_name()."""

    def test_accepts_simple_name(self):
        validate_name("quartus")

    def test_accepts_hyphenated_name(self):
        validate_name("quartus-prime")

    def test_accepts_name_with_digits(self):
        validate_name("tool2")

    def test_rejects_uppercase(self):
        with pytest.raises(click.BadParameter, match="lowercase"):
            validate_name("Quartus")

    def test_rejects_special_chars(self):
        with pytest.raises(click.BadParameter, match="lowercase letters, digits, and hyphens"):
            validate_name("my_plugin")

    def test_rejects_special_chars_dots(self):
        with pytest.raises(click.BadParameter, match="lowercase letters, digits, and hyphens"):
            validate_name("my.plugin")

    def test_rejects_starts_with_digit(self):
        with pytest.raises(click.BadParameter, match="start with a letter"):
            validate_name("2fast")

    def test_rejects_sawmill(self):
        with pytest.raises(click.BadParameter, match="cannot be 'sawmill'"):
            validate_name("sawmill")

    def test_rejects_empty(self):
        with pytest.raises(click.BadParameter, match="cannot be empty"):
            validate_name("")


class TestDeriveNames:
    """Tests for derive_names()."""

    def test_simple_name(self):
        names = derive_names("quartus")
        assert names["plugin_name"] == "quartus"
        assert names["package_name"] == "sawmill-plugin-quartus"
        assert names["module_name"] == "sawmill_plugin_quartus"
        assert names["class_name"] == "QuartusPlugin"
        assert names["entry_point_key"] == "quartus"
        assert names["directory_name"] == "sawmill-plugin-quartus"

    def test_hyphenated_name(self):
        names = derive_names("quartus-prime")
        assert names["plugin_name"] == "quartus-prime"
        assert names["package_name"] == "sawmill-plugin-quartus-prime"
        assert names["module_name"] == "sawmill_plugin_quartus_prime"
        assert names["class_name"] == "QuartusPrimePlugin"
        assert names["entry_point_key"] == "quartus-prime"
        assert names["directory_name"] == "sawmill-plugin-quartus-prime"

    def test_single_char_name(self):
        names = derive_names("x")
        assert names["class_name"] == "XPlugin"
        assert names["module_name"] == "sawmill_plugin_x"

    def test_name_with_digits(self):
        names = derive_names("tool2")
        assert names["class_name"] == "Tool2Plugin"
        assert names["module_name"] == "sawmill_plugin_tool2"
