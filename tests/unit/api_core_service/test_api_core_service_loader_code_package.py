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


def test_a_directory_is_accepted_only_when_the_caller_allows_it(tmp_path: Path) -> None:
    """Sprawdza, czy ścieżka katalogu jest przyjmowana wyłącznie z flagą `allow_dir=True`, wraca
    wtedy w jednej postaci także przy zapisie przez `..`, a sam katalog z kodem wraca jako `.`;
    plik przechodzi z flagą tak samo jak bez niej.

    Wyłapuje flagę, która niczego nie zmienia, oraz katalog przyjmowany bez niej: cytowanie
    i odczyt dostałyby ścieżkę katalogu i skończyły się błędem systemu plików zamiast odpowiedzią
    dla modelu."""
    package = _package(tmp_path)

    with pytest.raises(CodePathError, match="to katalog"):
        package.locate("src/lib/Numeracja")

    assert package.locate("src/lib/Numeracja", allow_dir=True)          == "src/lib/Numeracja"
    assert package.locate("src/lib/Sesja/../Numeracja", allow_dir=True) == "src/lib/Numeracja"
    assert package.locate(".", allow_dir=True)                          == "."
    assert package.locate(GENERATOR, allow_dir=True)                    == GENERATOR


@pytest.mark.parametrize("path", ["..", "../..", "/etc", "src/../../.."])
def test_a_directory_outside_the_package_is_refused_even_when_allowed(
    tmp_path: Path,
    path:     str,
) -> None:
    """Sprawdza, czy katalog leżący poza kodem, podany przez `..` albo ścieżką bezwzględną, kończy
    się wyjątkiem `CodePathError` także z flagą `allow_dir=True`.

    Wyłapuje flagę, która razem z katalogami wpuszcza wyjście poza paczkę: szukanie zawężone do
    takiej ścieżki przeszukiwałoby pliki kontenera, na przykład z hasłami."""
    with pytest.raises(CodePathError):
        _package(tmp_path).locate(path, allow_dir=True)


def test_a_missing_path_is_named_after_what_was_allowed(tmp_path: Path) -> None:
    """Sprawdza, czy komunikat o ścieżce, pod którą nic nie ma, mówi o pliku, a z flagą
    `allow_dir=True` o pliku albo katalogu, i w obu przypadkach powtarza ścieżkę od wołającego.

    Wyłapuje jeden komunikat na oba przypadki: model, który zawęził szukanie do katalogu,
    czytałby „nie ma takiego pliku" i szukał literówki w nazwie pliku, której nie podał."""
    package = _package(tmp_path)

    with pytest.raises(CodePathError, match="nie ma takiego pliku w kodzie aplikacji: src/brak"):
        package.locate("src/brak")

    with pytest.raises(CodePathError, match="nie ma takiego pliku ani katalogu.*src/brak"):
        package.locate("src/brak", allow_dir=True)


def test_the_code_directory_is_given_resolved(tmp_path: Path) -> None:
    """Sprawdza, czy `repo_dir()` oddaje katalog `repo/` paczki jako ścieżkę bezwzględną, bez
    dowiązań, także gdy paczkę podano przez dowiązanie do jej katalogu.

    Wyłapuje katalog oddawany w zapisie od wołającego: program szukający w kodzie ruszałby wtedy
    w innym katalogu niż ten, wobec którego czytnik sprawdza ścieżki."""
    _package(tmp_path)
    (tmp_path / "skrot").symlink_to(tmp_path / "paczka")

    assert CodePackage(tmp_path / "skrot").repo_dir() == (tmp_path / "paczka" / "repo").resolve()


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


def _package_with_a_tree(
    tmp_path: Path,  # katalog tymczasowy testu
) -> CodePackage:
    """
    Description:
    Buduje paczkę z plikami na trzech głębokościach, żeby było widać, że wyliczanie plików
    schodzi w podkatalogi: plik w katalogu głównym kodu, dwa w `src/lib` i jeden poziom niżej.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")

    Example result:
        CodePackage z plikami index.php, src/lib/b.php, src/lib/a.php i src/lib/Sesja/Kontrola.php
    """
    repo = tmp_path / "paczka" / "repo"

    for path in ("index.php", "src/lib/b.php", "src/lib/a.php", "src/lib/Sesja/Kontrola.php"):
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text("<?php\n", encoding="utf-8")

    (tmp_path / "haslo.yml").write_text(SECRET, encoding="utf-8")

    return CodePackage(tmp_path / "paczka")


def test_the_files_of_a_directory_are_listed_at_every_depth(tmp_path: Path) -> None:
    """Sprawdza, czy wyliczenie plików katalogu oddaje wszystkie pliki leżące pod nim, także
    w podkatalogach, jako ścieżki względne wobec kodu i po kolei alfabetycznie, a plik spoza
    tego katalogu pomija.

    Wyłapuje wyliczanie, które zatrzymuje się na pierwszym poziomie albo oddaje same nazwy:
    spis katalogu nie pokazałby wtedy zawartości podkatalogów, a ścieżki z niego nie dałoby
    się podać odczytowi pliku."""
    package = _package_with_a_tree(tmp_path)

    assert package.list_files("src/lib") == [
        "src/lib/Sesja/Kontrola.php",
        "src/lib/a.php",
        "src/lib/b.php",
    ]


def test_the_code_directory_itself_lists_the_whole_code(tmp_path: Path) -> None:
    """Sprawdza, czy wyliczenie plików dla ścieżki `.`, czyli samego katalogu z kodem, oddaje
    wszystkie pliki paczki, a katalog zapisany przez `..` daje to samo co zapisany wprost.

    Wyłapuje wyliczanie, które dla katalogu głównego oddaje ścieżki zaczynające się od `./`
    albo od położenia paczki na dysku: takiej ścieżki nie przyjmie żadne narzędzie kodu."""
    package = _package_with_a_tree(tmp_path)

    assert package.list_files(".") == [
        "index.php",
        "src/lib/Sesja/Kontrola.php",
        "src/lib/a.php",
        "src/lib/b.php",
    ]
    assert package.list_files("src/lib/Sesja/..") == package.list_files("src/lib")


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("src/lib/a.php", "to plik, nie katalog: src/lib/a.php"),
        ("src/brak",      "nie ma takiego pliku ani katalogu"),
        ("../..",         "wychodzi poza kod aplikacji"),
    ],
    ids=["plik", "brak katalogu", "poza paczką"],
)
def test_listing_something_that_is_not_a_directory_of_the_package_is_refused(
    tmp_path: Path,
    path:     str,
    message:  str,
) -> None:
    """Sprawdza, czy wyliczenie plików dla ścieżki pliku, dla katalogu, którego nie ma, i dla
    katalogu poza kodem kończy się wyjątkiem `CodePathError` z komunikatem nazywającym powód.

    Wyłapuje wyliczanie, które dla pliku oddaje pustą listę albo błąd systemu plików, oraz
    takie, które wychodzi poza paczkę: model zobaczyłby wtedy nazwy plików kontenera."""
    with pytest.raises(CodePathError, match=message):
        _package_with_a_tree(tmp_path).list_files(path)


def test_links_are_neither_listed_nor_followed(tmp_path: Path) -> None:
    """Sprawdza, czy wyliczenie plików pomija dowiązania: dowiązanie do pliku spoza paczki nie
    trafia na listę, a dowiązanie do katalogu spoza paczki nie jest przeszukiwane.

    Wyłapuje wyliczanie, które wchodzi w dowiązania: przez dowiązany katalog spis pokazałby
    nazwy plików spoza paczki, a dowiązanego pliku i tak nie dałoby się odczytać."""
    package = _package_with_a_tree(tmp_path)
    repo    = tmp_path / "paczka" / "repo"
    outside = tmp_path / "poza"

    outside.mkdir()
    (outside / "tajne.php").write_text(SECRET, encoding="utf-8")
    (repo / "src" / "lib" / "dowiazany-plik.php").symlink_to(tmp_path / "haslo.yml")
    (repo / "src" / "lib" / "dowiazany-katalog").symlink_to(outside, target_is_directory=True)

    assert package.list_files("src/lib") == [
        "src/lib/Sesja/Kontrola.php",
        "src/lib/a.php",
        "src/lib/b.php",
    ]


def test_listing_files_of_a_missing_package_is_a_deployment_error(tmp_path: Path) -> None:
    """Sprawdza, czy wyliczenie plików w paczce, której nie ma na dysku, kończy się wyjątkiem
    `CodePackageConfigError`, a nie `CodePathError`.

    Wyłapuje brak paczki zgłaszany jak brak katalogu: model dostawałby „nie ma takiego
    katalogu" na każdy spis, a błąd wdrożenia zostałby niezauważony."""
    with pytest.raises(CodePackageConfigError):
        CodePackage(tmp_path / "nie-ma").list_files(".")
