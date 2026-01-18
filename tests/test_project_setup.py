"""Tests for verifying the project structure and CLI entry point."""


def test_package_imports():
    """All core packages should be importable."""
    import sawmill
    import sawmill.core
    import sawmill.tui
    import sawmill.models
    import sawmill.utils


def test_cli_entry_point():
    """CLI should respond to --help."""
    from click.testing import CliRunner
    from sawmill.__main__ import cli
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'sawmill' in result.output.lower()
