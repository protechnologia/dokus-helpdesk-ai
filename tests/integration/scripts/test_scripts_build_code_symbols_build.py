"""
Description:
Testy integracyjne budowy mapy symboli (`scripts/build_code_symbols.py`) na małych paczkach
zakładanych w katalogu tymczasowym: które pliki trafiają do mapy, co zostaje po przerwanej
budowie i jak kończą się komendy. Mapę z aplikacji syntetycznej sprawdza osobny plik testów,
a wybieranie definicji z jednego pliku — testy jednostkowe.
"""

import json
from pathlib import Path

import build_code_symbols
import pytest
from build_code_package import cli as package_cli
from build_code_symbols import CODE_DIR, SYMBOLS_NAME, build_symbols, cli
from typer.testing import CliRunner

from tests._helpers.synthetic_code import SYNTHETIC_RULES_FILE, SYNTHETIC_SOURCE_DIR

GOOD_PHP = "<?php\nclass Numer\n{\n    public function nastepny()\n    {\n    }\n}\n"
BAD_PHP  = "<?php\nclass Zepsuta\n{\n    public function zla( {\n    }\n}\n"
GOOD_JS  = "APP.okna = {\n    zamknij: function () {\n    }\n};\n"


def _package(
    tmp_path: Path,            # katalog tymczasowy testu
    files:    dict[str, str],  # np. {"src/lib/Numer.php": "<?php\n…"}
) -> Path:
    """
    Description:
    Zakłada katalog paczki z podanymi plikami w `repo/`, czyli to, co zostawia skrypt paczki.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")
        files={"src/lib/Numer.php": "<?php\\nclass Numer\\n{…"}

    Example result:
        Path("/tmp/pytest-of-root/pytest-0/test_x0/paczka")
    """
    package = tmp_path / "paczka"
    for path, content in files.items():
        target = package / CODE_DIR / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    return package


def _names(
    package: Path,  # katalog paczki z zapisaną mapą
) -> dict[str, list[str]]:
    """
    Description:
    Czyta zapisaną mapę z dysku i oddaje dla każdego pliku nazwy jego symboli.

    Example args:
        package=Path("/tmp/pytest-of-root/pytest-0/test_x0/paczka")

    Example result:
        {"src/lib/Numer.php": ["Numer", "nastepny"]}
    """
    on_disk = json.loads((package / SYMBOLS_NAME).read_text(encoding="utf-8"))

    return {
        path: [symbol["name"] for symbol in symbols]
        for path, symbols in on_disk["files"].items()
    }


def test_only_php_and_js_files_enter_the_map(tmp_path: Path) -> None:
    """Sprawdza, czy do mapy trafiają pliki PHP i JS, także z rozszerzeniem zapisanym wielkimi
    literami, a szablon Twig, plik YAML i plik PHP bez żadnej definicji nie mają w niej wpisu
    ani nie stoją na liście plików odrzuconych.

    Wyłapuje rozbiór każdego pliku paczki parserem PHP: szablony i konfiguracja lądowałyby
    na liście błędów składni, a prawdziwy błąd składni ginąłby wśród nich."""
    package = _package(tmp_path, {
        "src/lib/Numer.php":         GOOD_PHP,
        "src/lib/STARY.PHP":         GOOD_PHP,
        "src/web/js/okna.js":        GOOD_JS,
        "src/lib/tresc.twig":        "{% block tresc %}{{ pismo.numer }}{% endblock %}\n",
        "src/config/routing.yml":    "pisma:\n  url: /pisma\n",
        "src/apps/szablon/lista.php": "<p><?php echo $numer ?></p>\n",
    })

    symbol_map = build_symbols(package)

    assert _names(package) == {
        "src/lib/Numer.php":  ["Numer", "nastepny"],
        "src/lib/STARY.PHP":  ["Numer", "nastepny"],
        "src/web/js/okna.js": ["zamknij"],
    }
    assert symbol_map.syntax_errors == []


def test_a_file_with_a_syntax_error_is_listed_and_the_rest_is_mapped(tmp_path: Path) -> None:
    """Sprawdza, czy plik z błędem składni trafia na listę plików odrzuconych i nie ma symboli,
    a pozostałe pliki paczki są w mapie jak zwykle.

    Wyłapuje budowę, która na jednym zepsutym pliku przerywa pracę albo po cichu go pomija:
    w pierwszym przypadku paczka zostaje bez mapy, w drugim nikt się nie dowie, że funkcji
    z tego pliku nie da się odczytać po nazwie."""
    package = _package(tmp_path, {
        "src/lib/Numer.php":   GOOD_PHP,
        "src/lib/Zepsuta.php": BAD_PHP,
    })

    symbol_map = build_symbols(package)

    assert symbol_map.syntax_errors == ["src/lib/Zepsuta.php"]
    assert _names(package) == {"src/lib/Numer.php": ["Numer", "nastepny"]}


def test_a_rebuild_forgets_a_file_removed_from_the_package(tmp_path: Path) -> None:
    """Sprawdza, czy po usunięciu pliku z paczki ponowna budowa daje mapę bez jego symboli.

    Wyłapuje budowę, która dopisuje do poprzedniej mapy: zostawałyby w niej funkcje z plików,
    których w kodzie już nie ma."""
    package = _package(tmp_path, {"src/lib/Numer.php": GOOD_PHP, "src/web/js/okna.js": GOOD_JS})

    build_symbols(package)
    (package / CODE_DIR / "src/web/js/okna.js").unlink()
    build_symbols(package)

    assert _names(package) == {"src/lib/Numer.php": ["Numer", "nastepny"]}


def test_an_interrupted_build_leaves_no_map_of_the_previous_code(
    tmp_path:    Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy budowa przerwana w trakcie rozbioru plików nie zostawia w katalogu paczki
    mapy z poprzedniej budowy.

    Wyłapuje kasowanie starej mapy dopiero przy zapisie nowej: po przebudowie kodu i nieudanej
    budowie mapy narzędzia czytałyby granice funkcji ze starego kodu, bez żadnego błędu."""
    package = _package(tmp_path, {"src/lib/Numer.php": GOOD_PHP})
    build_symbols(package)

    def interrupted(path: str, content: bytes) -> None:
        """Udaje rozbiór pliku przerwany w połowie budowy."""
        raise KeyboardInterrupt

    monkeypatch.setattr(build_code_symbols, "symbols_of_file", interrupted)
    with pytest.raises(KeyboardInterrupt):
        build_symbols(package)

    assert not (package / SYMBOLS_NAME).exists()


def test_a_directory_without_a_package_is_refused_and_left_alone(tmp_path: Path) -> None:
    """Sprawdza, czy budowa mapy w katalogu bez `repo/` kończy się błędem i nie rusza pliku
    o nazwie mapy, który tam leży.

    Wyłapuje skrypt, który przy pomylonym katalogu kasuje plik albo zapisuje pustą mapę:
    pusta mapa wyglądałaby jak paczka, w której nie ma ani jednej funkcji."""
    wrong = tmp_path / "nie-paczka"
    wrong.mkdir()
    (wrong / SYMBOLS_NAME).write_text("cudzy plik", encoding="utf-8")

    with pytest.raises(ValueError, match="Nie ma paczki"):
        build_symbols(wrong)

    assert (wrong / SYMBOLS_NAME).read_text(encoding="utf-8") == "cudzy plik"


def test_the_command_reports_the_map_and_fails_without_a_package(tmp_path: Path) -> None:
    """Sprawdza komendę `build`: dla paczki kończy się kodem 0 i wypisuje, ile symboli w ilu
    plikach zapisała oraz który plik parser odrzucił, a dla katalogu bez paczki kończy się
    kodem 1.

    Wyłapuje komendę, która zawsze kończy się powodzeniem albo nie mówi o pliku z błędem
    składni: procedura budowy paczki nie zauważyłaby, że mapy nie ma albo jest niepełna."""
    runner  = CliRunner()
    package = _package(tmp_path, {
        "src/lib/Numer.php":   GOOD_PHP,
        "src/lib/Zepsuta.php": BAD_PHP,
    })

    built   = runner.invoke(cli, ["build", str(package)])
    missing = runner.invoke(cli, ["build", str(tmp_path / "nie-ma")])

    assert (built.exit_code, missing.exit_code) == (0, 1)
    assert "2 symboli w 1 plikach" in built.output
    assert "src/lib/Zepsuta.php" in built.output


def test_building_a_package_builds_its_map_and_replaces_a_stale_one(tmp_path: Path) -> None:
    """Sprawdza, czy komenda budowy paczki kodu zapisuje w katalogu paczki mapę symboli nowego
    kodu, także wtedy, gdy leżała tam mapa innego kodu, i wypisuje jej podsumowanie.

    Wyłapuje budowę paczki, która mapy nie rusza: po przebudowie kodu narzędzia czytałyby
    granice funkcji z poprzedniej wersji plików."""
    package = _package(tmp_path, {"src/lib/Stary.php": GOOD_PHP})
    build_symbols(package)
    (package / "manifest.json").write_text("{}", encoding="utf-8")

    result = CliRunner().invoke(
        package_cli,
        ["build", str(SYNTHETIC_SOURCE_DIR), str(package), "--rules", str(SYNTHETIC_RULES_FILE)],
    )

    names = _names(package)

    assert result.exit_code == 0, result.output
    assert "Mapa symboli:" in result.output
    assert "src/lib/Stary.php" not in names
    assert names["src/lib/Urzad/Numeracja/GeneratorNumeru.php"] == [
        "GeneratorNumeru",
        "nastepnyNumer",
    ]
