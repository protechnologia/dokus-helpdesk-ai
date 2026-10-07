from pathlib import Path

import pytest

from app.core_service.loader_code_package import (
    CodePackage,
    CodePackageConfigError,
    CodePathError,
    split_lines,
)

# Paczka kodu to katalog z podkatalogiem `repo/`. Testy budują ją w katalogu tymczasowym, więc nie
# potrzebują paczki zbudowanej skryptem.

GENERATOR = "src/lib/Numeracja/GeneratorNumeru.php"
SECRET    = "tajne-haslo-do-bazy"


def _package(
    tmp_path: Path,  # katalog tymczasowy testu
) -> CodePackage:
    """
    Description:
    Buduje małą paczkę kodu: jeden plik PHP w `repo/`, a obok paczki plik z hasłem, do którego
    paczka nie może dać dostępu.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")

    Example result:
        CodePackage czytająca z <tmp_path>/paczka/repo
    """
    root = tmp_path / "paczka"
    file = root / "repo" / GENERATOR

    file.parent.mkdir(parents=True)
    file.write_text("<?php\n\nclass GeneratorNumeru\n{\n}\n", encoding="utf-8")
    (tmp_path / "haslo.yml").write_text(SECRET, encoding="utf-8")

    return CodePackage(root)


def test_a_path_inside_the_package_comes_back_in_one_form(tmp_path: Path) -> None:
    """Sprawdza, czy ta sama ścieżka zapisana na dwa sposoby, wprost i przez `..`, wraca jako jedna
    i ta sama ścieżka względna wobec kodu.

    Wyłapuje ścieżkę oddawaną tak, jak ją zapisano: po ścieżce powstaje identyfikator źródła,
    więc ten sam plik podany dwoma zapisami stałby na liście źródeł dwa razy."""
    package = _package(tmp_path)

    assert package.locate(GENERATOR)                                      == GENERATOR
    assert package.locate("src/lib/Sesja/../Numeracja/GeneratorNumeru.php") == GENERATOR


@pytest.mark.parametrize(
    "path",
    [
        "../../haslo.yml",                 # wyjście w górę przez `..`
        "src/../../../haslo.yml",          # to samo, zaczęte wewnątrz paczki
        "/etc/passwd",                     # ścieżka bezwzględna
    ],
)
def test_a_path_leaving_the_package_is_refused(tmp_path: Path, path: str) -> None:
    """Sprawdza, czy ścieżka prowadząca poza katalog z kodem (przez `..` albo bezwzględna) kończy
    się wyjątkiem `CodePathError`, także gdy pod tą ścieżką leży prawdziwy plik.

    Wyłapuje czytnik, który składa ścieżkę od modelu z katalogiem paczki bez sprawdzenia, dokąd
    ona prowadzi: model mógłby wtedy wskazać dowolny plik kontenera, na przykład z hasłami."""
    with pytest.raises(CodePathError):
        _package(tmp_path).locate(path)


def test_a_link_leading_out_of_the_package_is_refused(tmp_path: Path) -> None:
    """Sprawdza, czy dowiązanie leżące w paczce, ale wskazujące plik poza nią, kończy się wyjątkiem
    `CodePathError` przy wyszukaniu i przy odczycie.

    Wyłapuje sprawdzanie granicy na samym zapisie ścieżki: zapis mieści się w paczce, a plik, do
    którego prowadzi, już nie, więc treść spoza paczki wyszłaby do modelu."""
    package = _package(tmp_path)
    link    = tmp_path / "paczka" / "repo" / "src" / "dowiazanie.php"

    link.symlink_to(tmp_path / "haslo.yml")

    with pytest.raises(CodePathError):
        package.locate("src/dowiazanie.php")

    with pytest.raises(CodePathError):
        package.read_lines("src/dowiazanie.php")


@pytest.mark.parametrize(
    "path",
    [
        "src/lib/Numeracja",               # katalog
        "src/lib/Numeracja/Brak.php",      # nic pod ścieżką
        "",                                # pusta ścieżka: sam katalog z kodem
        "src/lib/\x00.php",                # znak zerowy
        "x" * 5000,                        # nazwa dłuższa, niż przyjmuje system plików
    ],
)
def test_a_path_that_is_not_a_file_is_refused(tmp_path: Path, path: str) -> None:
    """Sprawdza, czy ścieżka wskazująca katalog, nieistniejący plik albo zapis, którego system
    plików nie przyjmuje, kończy się wyjątkiem `CodePathError`.

    Wyłapuje czytnik, który na dziwną ścieżkę od modelu odpowiada błędem systemu plików zamiast
    własnym: taki błąd nie wróciłby do modelu jako podpowiedź, tylko przerwał całe żądanie."""
    with pytest.raises(CodePathError):
        _package(tmp_path).locate(path)


def test_the_refusal_does_not_say_where_the_package_lies(tmp_path: Path) -> None:
    """Sprawdza, czy komunikat odmowy powtarza ścieżkę w brzmieniu od wołającego i nie zawiera
    położenia paczki na dysku.

    Wyłapuje komunikat ze ścieżką bezwzględną: wraca on do modelu, więc zdradzałby układ katalogów
    serwera, a model mógłby go użyć w następnym wywołaniu."""
    with pytest.raises(CodePathError) as caught:
        _package(tmp_path).locate("src/lib/Numeracja/Brak.php")

    assert "src/lib/Numeracja/Brak.php" in str(caught.value)
    assert str(tmp_path) not in str(caught.value)


def test_lines_come_back_numbered_like_in_the_file(tmp_path: Path) -> None:
    """Sprawdza, czy odczyt pliku oddaje jego linie po kolei, bez znaków końca linii i bez pustej
    linii dopisanej po końcu pliku: plik z pięcioma liniami daje pięć elementów.

    Wyłapuje przesunięcie numeracji: narzędzia podają i przyjmują numery linii, więc linia więcej
    albo mniej oznacza cytowanie innego miejsca, niż model wskazał."""
    lines = _package(tmp_path).read_lines(GENERATOR)

    assert lines == ["<?php", "", "class GeneratorNumeru", "{", "}"]


def test_only_the_newline_splits_lines() -> None:
    """Sprawdza, czy treść jest dzielona na linie wyłącznie znakiem nowej linii: znak końca strony
    w środku linii jej nie dzieli, a tekst bez znaku nowej linii na końcu ma ostatnią linię
    w całości.

    Wyłapuje podział funkcją, która tnie także na innych znakach: numery linii przestałyby się
    wtedy zgadzać z numerami z szukania i z edytora."""
    assert split_lines("jedna\x0cnadal jedna\ndruga") == ["jedna\x0cnadal jedna", "druga"]
    assert split_lines("jedna\ndruga\n")              == ["jedna", "druga"]
    assert split_lines("")                            == []


def test_a_missing_package_is_a_deployment_error(tmp_path: Path) -> None:
    """Sprawdza, czy paczka wskazująca katalog, którego nie ma, kończy wyszukanie pliku wyjątkiem
    `CodePackageConfigError`, a nie `CodePathError`.

    Wyłapuje brak paczki zgłaszany jak brak pliku: model dostawałby „nie ma takiego pliku" na
    każde pytanie i uznawał, że kod nic nie mówi, a błąd wdrożenia zostałby niezauważony."""
    with pytest.raises(CodePackageConfigError):
        CodePackage(tmp_path / "nie-ma").locate(GENERATOR)


def test_building_the_package_does_not_touch_the_disk(tmp_path: Path) -> None:
    """Sprawdza, czy zbudowanie obiektu paczki dla katalogu, którego nie ma, nie kończy się
    błędem.

    Wyłapuje sprawdzanie dysku w konstruktorze: narzędzia buduje się raz na proces, razem z tymi
    na bazach, i instancja bez paczki kodu nie mogłaby wtedy obsłużyć żadnej sprawy."""
    CodePackage(tmp_path / "nie-ma")
