"""
Description:
Test integracyjny sprawdzania opisu projektu w skrypcie paczki kodu
(`scripts/build_code_package.py`): opis w katalogu paczki wobec plików w `repo/`. Na małych
drzewach plików w katalogu tymczasowym i na aplikacji syntetycznej. Bez stacku i bez modelu.

| co                                            | czego pilnuje test                         |
|-----------------------------------------------|--------------------------------------------|
| ścieżka z opisu, której w paczce nie ma        | jest zgłoszona                             |
| ścieżka z sekcji „Czego w paczce nie ma"       | zgłoszona, gdy w paczce jest               |
| `<nazwa>` i `*` w ścieżce, ukośnik na końcu    | zastępują jedną nazwę; ukośnik to katalog  |
| brak pliku opisu                               | wynik mówi o braku, komenda kończy kodem 1 |
| opis aplikacji syntetycznej z repo             | zgadza się z paczką z jej źródła           |
"""

from pathlib import Path

import pytest
from build_code_package import (
    CODE_DIR,
    DESCRIPTION_NAME,
    build_package,
    check_description,
    cli,
    is_in_package,
    load_rules,
    paths_of_description,
)
from typer.testing import CliRunner

from app.core_util.markdown import read_document
from tests.helpers_code_package import (
    SYNTHETIC_PACKAGE_DIR,
    SYNTHETIC_RULES_FILE,
    SYNTHETIC_SOURCE_DIR,
)

FILES = [
    "src/web/index.php",
    "src/web/js/_global/bledy.js",
    "src/apps/frontend/modules/pisma/actions/actions.class.php",
    "src/apps/admin/modules/konta/actions/actions.class.php",
    "src/config/doctrine/schema_pisma.yml",
]


def _package(
    tmp_path:    Path,               # katalog tymczasowy testu
    description: str | None = None,  # treść `project.md`; None: pliku nie ma
) -> Path:
    """
    Description:
    Zakłada katalog paczki z kilkoma plikami w `repo/` i, jeśli podano, z opisem projektu.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")
        description="Kod w `src/web/js/`."

    Example result:
        Path("/tmp/pytest-of-root/pytest-0/test_x0/paczka")
    """
    root = tmp_path / "paczka"

    for path in FILES:
        (root / CODE_DIR / path).parent.mkdir(parents=True, exist_ok=True)
        (root / CODE_DIR / path).write_text("<?php\n", encoding="utf-8")

    if description is not None:
        (root / DESCRIPTION_NAME).write_text(description, encoding="utf-8")

    return root


def test_a_description_that_matches_the_package_is_ok(tmp_path: Path) -> None:
    """Sprawdza, czy opis, którego każda ścieżka istnieje w paczce, a ścieżka z sekcji „Czego
    w paczce nie ma" w niej nie istnieje, przechodzi sprawdzenie bez uwag i z policzoną
    długością.

    Wyłapuje sprawdzenie, które zgłasza poprawny opis: po kilku fałszywych alarmach nikt nie
    czytałby jego wyniku."""
    text = "Wejście `src/web/index.php`, JS w `src/web/js/`.\n## Czego w paczce nie ma\n`src/x/`\n"

    check = check_description(_package(tmp_path, text))

    assert check.ok
    assert (check.missing, check.unexpected) == ([], [])
    assert check.chars == len(text.rstrip())


def test_a_path_that_leads_nowhere_is_reported(tmp_path: Path) -> None:
    """Sprawdza, czy ścieżka z opisu, której w paczce nie ma, trafia na listę brakujących,
    a ścieżki istniejące na nią nie trafiają.

    Wyłapuje opis napisany dla innej gałęzi kodu: model wziąłby z niego katalog, którego
    w paczce nie ma, i dostał błąd od spisu albo szukania."""
    text = "JS w `src/web/js/`, stare okna w `src/web/js/_okienka/`."

    check = check_description(_package(tmp_path, text))

    assert not check.ok
    assert check.missing == ["src/web/js/_okienka/"]


def test_a_path_said_to_be_absent_but_present_is_reported(tmp_path: Path) -> None:
    """Sprawdza, czy ścieżka z sekcji „Czego w paczce nie ma", która w paczce jednak jest,
    trafia na osobną listę.

    Wyłapuje opis nieaktualny po zmianie reguł paczki: mówiłby modelowi, że schematów tabel nie
    przeczyta, choć weszły do paczki, więc model by ich nie szukał."""
    text = "JS w `src/web/js/`.\n## Czego w paczce nie ma\nSchematów (`src/config/doctrine/`).\n"

    check = check_description(_package(tmp_path, text))

    assert not check.ok
    assert (check.missing, check.unexpected) == ([], ["src/config/doctrine/"])


def test_an_editorial_comment_is_not_checked(tmp_path: Path) -> None:
    """Sprawdza, czy ścieżka stojąca w komentarzu redakcyjnym opisu nie jest sprawdzana.

    Wyłapuje sprawdzenie, które czyta opis inaczej niż usługa: komentarz do modelu nie trafia,
    więc notatka „usunięto `src/stare/`" nie może uchodzić za błąd opisu."""
    text = "<!-- usunięto `src/stare/` -->\nJS w `src/web/js/`."

    assert check_description(_package(tmp_path, text)).ok


@pytest.mark.parametrize(
    ("path", "found"),
    [
        ("src/web/index.php",                     True),
        ("src/web/js/",                           True),
        ("src/web/index.php/",                    False),
        ("src/apps/<aplikacja>/modules/",         True),
        ("src/apps/<aplikacja>/modules/<moduł>/", True),
        ("src/apps/*/modules/pisma/",             True),
        ("src/apps/<aplikacja>/config/app.yml",   False),
        ("src/config/doctrine/schema_<temat>.yml", True),
        ("src/web/../../../../haslo.yml",         False),
    ],
    ids=[
        "plik", "katalog", "plik z ukośnikiem", "nazwa w nawiasach", "dwie nazwy", "gwiazdka",
        "brak pliku pod wzorcem", "nazwa w środku pliku", "wyjście poza paczkę",
    ],
)
def test_how_a_path_of_the_description_is_matched(tmp_path: Path, path: str, found: bool) -> None:
    """Sprawdza, jak ścieżka z opisu jest dopasowywana do paczki: plik i katalog wprost,
    `<nazwa>` i `*` jako jedna dowolna nazwa, ukośnik na końcu jako wymóg katalogu, a ścieżka
    z `..` nigdy nie pasuje.

    Wyłapuje dopasowanie, które bierze plik za katalog albo wychodzi poza paczkę: opis
    przechodziłby sprawdzenie dzięki plikowi, który leży obok paczki, a nie w niej."""
    package = _package(tmp_path)
    # Plik obok paczki: cztery poziomy w górę od `repo/src/web`.
    (tmp_path / "haslo.yml").write_text("tajne", encoding="utf-8")

    assert is_in_package(package / CODE_DIR, path) is found


def test_a_missing_description_is_said_plainly(tmp_path: Path) -> None:
    """Sprawdza, czy sprawdzenie paczki bez pliku opisu oddaje wynik „opisu nie ma", który nie
    jest poprawny, zamiast błędu albo pustego wyniku bez uwag.

    Wyłapuje brak opisu uznany za opis bez zastrzeżeń: narzędzie `describe_code` zatrzymuje
    wtedy sprawę błędem konfiguracji, a budowa paczki nic by o tym nie powiedziała."""
    check = check_description(_package(tmp_path))

    assert (check.found, check.ok) == (False, False)


def test_a_directory_without_a_built_package_is_refused(tmp_path: Path) -> None:
    """Sprawdza, czy sprawdzenie katalogu, w którym nie ma `repo/`, kończy się wyjątkiem
    `ValueError`.

    Wyłapuje sprawdzenie, które na pustym katalogu zgłasza każdą ścieżkę jako brakującą:
    literówka w nazwie katalogu paczki wyglądałaby jak całkiem błędny opis."""
    with pytest.raises(ValueError, match="nie ma zbudowanej paczki"):
        check_description(tmp_path)


def test_the_command_fails_when_the_description_does_not_match(tmp_path: Path) -> None:
    """Sprawdza komendę `check-description`: dla opisu zgodnego z paczką kończy się kodem 0,
    a dla opisu ze ścieżką donikąd i dla paczki bez opisu kodem 1, wypisując, czego dotyczy
    uwaga.

    Wyłapuje komendę, która zawsze kończy się powodzeniem: sprawdzenie wpięte w skrypt albo
    w ręczną procedurę nie zatrzymałoby nieaktualnego opisu."""
    runner  = CliRunner()
    good    = _package(tmp_path / "dobra", "JS w `src/web/js/`.")
    wrong   = _package(tmp_path / "zla", "JS w `src/web/skrypty/`.")
    without = _package(tmp_path / "bez")

    ok      = runner.invoke(cli, ["check-description", str(good)])
    bad     = runner.invoke(cli, ["check-description", str(wrong)])
    missing = runner.invoke(cli, ["check-description", str(without)])

    assert (ok.exit_code, bad.exit_code, missing.exit_code) == (0, 1, 1)
    assert "src/web/skrypty/" in bad.output
    assert "BRAK" in missing.output


def test_a_build_reports_the_description_and_does_not_touch_it(tmp_path: Path) -> None:
    """Sprawdza, czy budowa paczki z aplikacji syntetycznej zostawia plik opisu w katalogu
    paczki bez zmian i wypisuje wynik jego sprawdzenia, a brak zgodności budowy nie zatrzymuje.

    Wyłapuje budowę, która kasuje opis razem z `repo/` albo kończy się błędem przez opis:
    opis pisze człowiek, więc przebudowa paczki nie może go ani zgubić, ani od niego zależeć."""
    package     = tmp_path / "paczka"
    description = package / DESCRIPTION_NAME
    text        = "JS w `src/web/js/`, a tego nie ma: `src/brak/`."

    package.mkdir()
    description.write_text(text, encoding="utf-8")

    result = CliRunner().invoke(
        cli,
        ["build", str(SYNTHETIC_SOURCE_DIR), str(package), "--rules", str(SYNTHETIC_RULES_FILE)],
    )

    assert result.exit_code == 0, result.output
    assert description.read_text(encoding="utf-8") == text
    assert "src/brak/" in result.output


def test_the_description_of_the_synthetic_application_matches_its_package(tmp_path: Path) -> None:
    """Sprawdza, czy opis aplikacji syntetycznej z repo (`data/safe/code/project.md`) zgadza się
    z paczką zbudowaną z jej źródła: każda ścieżka z opisu istnieje w paczce i opis wymienia
    przynajmniej trzy ścieżki.

    Wyłapuje opis rozjechany ze źródłem po zmianie nazwy katalogu: testy narzędzia
    `describe_code` czytają ten opis, więc model w teście dostawałby katalog, którego nie ma."""
    package = tmp_path / "paczka"

    build_package(SYNTHETIC_SOURCE_DIR, package, load_rules(SYNTHETIC_RULES_FILE))
    (package / DESCRIPTION_NAME).write_text(
        (SYNTHETIC_PACKAGE_DIR / DESCRIPTION_NAME).read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    check    = check_description(package)
    named, _ = paths_of_description(read_document(package / DESCRIPTION_NAME), {"src"})

    assert check.ok, (check.missing, check.unexpected)
    assert len(named) >= 3
