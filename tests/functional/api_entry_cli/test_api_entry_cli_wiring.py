from typer.testing import CliRunner

from app.entry_cli.cli import cli

runner = CliRunner()


def test_help_lists_the_command_tree() -> None:
    """Sprawdza, czy `helpdesk --help` kończy się kodem 0 i wypisuje listę komend, na której jest
    `version`.

    Wyłapuje drzewo komend, które się nie składa albo zwija do jednej komendy: operator nie
    zobaczyłby wtedy w pomocy, jakie komendy są dostępne."""
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "version" in result.output


def test_help_shows_curated_text_not_the_docstring() -> None:
    """Sprawdza, czy w wyniku `helpdesk --help` nie ma słowa „Description:", od którego zaczynają
    się nasze docstringi pisane dla programisty.

    Wyłapuje komendę zarejestrowaną bez własnego tekstu pomocy (`help=`): Typer wstawia wtedy do
    pomocy docstring funkcji i operator czyta notatki dla programisty zamiast opisu komendy."""
    result = runner.invoke(cli, ["--help"])

    assert "Description:" not in result.output


def test_version_command_runs() -> None:
    """Sprawdza, czy `helpdesk version` kończy się kodem 0 i wypisuje nazwę pakietu
    `dokus-helpdesk-ai`.

    Wyłapuje zepsute podpięcie CLI: komendę, której nie da się uruchomić, albo pakiet
    zainstalowany tak, że nie da się odczytać jego wersji."""
    result = runner.invoke(cli, ["version"])

    assert result.exit_code == 0
    assert "dokus-helpdesk-ai" in result.output
