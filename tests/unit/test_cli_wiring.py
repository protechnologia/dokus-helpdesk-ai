from typer.testing import CliRunner

from app.cli.cli import cli

runner = CliRunner()


def test_help_lists_the_command_tree() -> None:
    """`dokus --help` → exit 0 and the subcommand section (Typer stayed in tree mode)."""
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "version" in result.output


def test_help_shows_curated_text_not_the_docstring() -> None:
    """Command help → the text from `help=`, never our internal docstring format."""
    result = runner.invoke(cli, ["--help"])

    assert "Description:" not in result.output


def test_version_command_runs() -> None:
    """`dokus version` → exit 0 and the package name in the output (entry point wiring works)."""
    result = runner.invoke(cli, ["version"])

    assert result.exit_code == 0
    assert "dokus-helpdesk-ai" in result.output
