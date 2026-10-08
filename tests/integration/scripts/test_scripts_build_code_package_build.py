"""
Description:
Testy integracyjne budowy paczki kodu (`scripts/build_code_package.py`) na małych drzewach
plików w katalogu tymczasowym: co skrypt robi z katalogiem paczki i kiedy odmawia.

| sytuacja                                            | oczekiwanie                          |
|-----------------------------------------------------|--------------------------------------|
| do paczki nie wszedłby żaden plik                   | błąd, poprzednia paczka zostaje      |
| `repo/` bez metryczki obok                          | błąd, katalog zostaje                |
| plik zniknął ze źródła                              | po ponownej budowie znika z paczki   |
| pozostałość `repo.building/` po przerwanej budowie  | nie trafia do paczki                 |
| plik nie w UTF-8                                    | pominięty i wypisany w metryczce     |
| folder z reguł nie istnieje, zły klucz w regułach   | błąd                                 |

Dobór plików na regułach aplikacji syntetycznej sprawdza sąsiedni plik testów; tu reguły są
najprostsze z możliwych: pliki PHP z jednego folderu.
"""

import dataclasses
import json
from pathlib import Path

import pytest
from build_code_package import (
    BUILDING_DIR,
    CODE_DIR,
    MANIFEST_NAME,
    Rules,
    build_package,
    load_rules,
)

RULES = Rules(
    extensions       = ("php",),
    folders          = ("src/lib",),
    files            = (),
    excluded_folders = (),
    excluded_files   = (),
)

NUMER = "src/lib/Numer.php"
STARY = "src/lib/Stary.php"

# Polskie litery w kodowaniu Windows: te bajty nie są poprawnym UTF-8.
NOT_UTF8 = "<?php // zażółć".encode("cp1250")

VALID_RULES_FILE = {
    "extensions":       ["php"],
    "folders":          ["src/lib"],
    "files":            [],
    "excluded_folders": ["vendor"],
    "excluded_files":   [],
}


def _source(
    tmp_path: Path,              # katalog tymczasowy testu
    files:    dict[str, bytes],  # np. {"src/lib/Numer.php": b"<?php\n"}
) -> Path:
    """
    Description:
    Zakłada folder wejściowy z podanymi plikami, czyli to, co skrypt dostaje jako kod aplikacji.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")
        files={"src/lib/Numer.php": b"<?php\\n"}

    Example result:
        Path("/tmp/pytest-of-root/pytest-0/test_x0/kod")
    """
    source = tmp_path / "kod"
    for path, content in files.items():
        (source / path).parent.mkdir(parents=True, exist_ok=True)
        (source / path).write_bytes(content)

    return source


def _package_files(
    package_dir: Path,  # np. Path("/tmp/pytest-of-root/pytest-0/test_x0/paczka")
) -> set[str]:
    """
    Description:
    Zbiera ścieżki plików z `repo/` paczki, liczone od `repo/`.

    Example args:
        package_dir=Path("/tmp/pytest-of-root/pytest-0/test_x0/paczka")

    Example result:
        {"src/lib/Numer.php"}
    """
    repo = package_dir / CODE_DIR

    return {path.relative_to(repo).as_posix() for path in repo.rglob("*") if path.is_file()}


def test_a_build_with_no_readable_file_keeps_the_previous_package(tmp_path: Path) -> None:
    """Sprawdza, czy budowa, w której jedyny wybrany plik nie jest w UTF-8, kończy się błędem,
    a poprzednio zbudowana paczka i jej metryczka zostają na dysku bez zmian.

    Wyłapuje skrypt, który kasuje starą paczkę, zanim sprawdzi, czy ma czym ją zastąpić:
    narzędzia agenta zostałyby bez kodu, a obok leżałaby metryczka mówiąca, że kod jest."""
    source      = _source(tmp_path, {NUMER: b"<?php // pierwsza wersja\n"})
    package_dir = tmp_path / "paczka"
    build_package(source, package_dir, RULES)
    manifest_before = (package_dir / MANIFEST_NAME).read_bytes()

    (source / NUMER).write_bytes(NOT_UTF8)

    with pytest.raises(ValueError, match="nie wszedł żaden plik"):
        build_package(source, package_dir, RULES)

    assert (package_dir / CODE_DIR / NUMER).read_bytes() == b"<?php // pierwsza wersja\n"
    assert (package_dir / MANIFEST_NAME).read_bytes()    == manifest_before


def test_rules_that_select_nothing_do_not_leave_an_empty_package(tmp_path: Path) -> None:
    """Sprawdza, czy budowa według reguł, które nie wybierają żadnego pliku, kończy się błędem
    i nie zostawia ani katalogu `repo/`, ani metryczki.

    Wyłapuje pustą paczkę przyjętą jako wynik: przy literówce w rozszerzeniu narzędzia agenta
    odpowiadałyby na każde pytanie o kod, że takiego pliku nie ma."""
    source      = _source(tmp_path, {NUMER: b"<?php\n"})
    package_dir = tmp_path / "paczka"
    rules       = dataclasses.replace(RULES, extensions=("twig",))

    with pytest.raises(ValueError, match="nie wszedł żaden plik"):
        build_package(source, package_dir, rules)

    assert not (package_dir / CODE_DIR).exists()
    assert not (package_dir / MANIFEST_NAME).exists()


def test_a_repo_directory_the_script_did_not_build_is_not_deleted(tmp_path: Path) -> None:
    """Sprawdza, czy skrypt odmawia budowy w katalogu, w którym jest `repo/`, ale nie ma obok
    metryczki, i zostawia zawartość tego katalogu.

    Wyłapuje skrypt, który kasuje każdy katalog `repo/` w podanym miejscu: pomyłka w drugim
    argumencie komendy usuwałaby cudze pliki."""
    source      = _source(tmp_path, {NUMER: b"<?php\n"})
    package_dir = tmp_path / "nie-paczka"
    foreign     = package_dir / CODE_DIR / "wazne.txt"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("cudzy plik", encoding="utf-8")

    with pytest.raises(ValueError, match=MANIFEST_NAME):
        build_package(source, package_dir, RULES)

    assert foreign.read_text(encoding="utf-8") == "cudzy plik"


def test_a_rebuild_drops_a_file_removed_from_the_source(tmp_path: Path) -> None:
    """Sprawdza, czy po usunięciu pliku ze źródła i ponownej budowie w paczce zostaje tylko to,
    co jest w źródle, a metryczka liczy jeden plik.

    Wyłapuje budowę, która dokłada pliki do istniejącej paczki, zamiast ją zastąpić: model
    czytałby kod, którego w aplikacji już nie ma."""
    source      = _source(tmp_path, {NUMER: b"<?php\n", STARY: b"<?php\n"})
    package_dir = tmp_path / "paczka"
    build_package(source, package_dir, RULES)

    (source / STARY).unlink()
    manifest = build_package(source, package_dir, RULES)

    assert _package_files(package_dir) == {NUMER}
    assert manifest.package.files      == 1


def test_leftovers_of_an_interrupted_build_do_not_enter_the_package(tmp_path: Path) -> None:
    """Sprawdza, czy plik zostawiony w `repo.building/` przez przerwaną budowę nie trafia do
    paczki i czy po budowie katalogu tymczasowego już nie ma.

    Wyłapuje budowę, która kopiuje pliki do zastanego katalogu tymczasowego: po przerwanym
    przebiegu w paczce zostawałby plik, którego reguły już nie wybierają."""
    source      = _source(tmp_path, {NUMER: b"<?php\n"})
    package_dir = tmp_path / "paczka"
    leftover    = package_dir / BUILDING_DIR / "src/lib/Porzucony.php"
    leftover.parent.mkdir(parents=True)
    leftover.write_bytes(b"<?php\n")

    build_package(source, package_dir, RULES)

    assert _package_files(package_dir) == {NUMER}
    assert not (package_dir / BUILDING_DIR).exists()


def test_a_file_that_is_not_utf8_is_skipped_and_reported(tmp_path: Path) -> None:
    """Sprawdza, czy wybrany plik w innym kodowaniu niż UTF-8 nie wchodzi do paczki, jest
    wypisany w metryczce jako pominięty i nie jest liczony wśród plików paczki.

    Wyłapuje plik w kodowaniu Windows skopiowany do paczki albo pominięty po cichu: narzędzia
    czytają paczkę jako UTF-8, więc albo odczyt by się wywracał, albo nikt by nie wiedział, że
    model tego pliku nie dostaje."""
    source      = _source(tmp_path, {NUMER: b"<?php\n", STARY: NOT_UTF8})
    package_dir = tmp_path / "paczka"

    manifest = build_package(source, package_dir, RULES)

    assert _package_files(package_dir) == {NUMER}
    assert manifest.skipped.not_utf8   == [STARY]
    assert manifest.package.files      == 1


def test_a_folder_from_the_rules_missing_in_the_source_is_an_error(tmp_path: Path) -> None:
    """Sprawdza, czy budowa według reguł wymieniających folder, którego nie ma w folderze
    wejściowym, kończy się błędem z nazwą tego folderu i nie tworzy paczki.

    Wyłapuje literówkę w nazwie folderu przyjętą bez błędu: paczka powstałaby mniejsza
    o cały folder kodu i nic by na to nie wskazywało."""
    source      = _source(tmp_path, {NUMER: b"<?php\n"})
    package_dir = tmp_path / "paczka"
    rules       = dataclasses.replace(RULES, folders=("src/lib", "src/brak"))

    with pytest.raises(ValueError, match="src/brak"):
        build_package(source, package_dir, rules)

    assert not (package_dir / CODE_DIR).exists()


@pytest.mark.parametrize(
    "rules_file",
    [
        {key: value for key, value in VALID_RULES_FILE.items() if key != "excluded_folders"},
        {**VALID_RULES_FILE, "komentarz": "reguły dla aplikacji"},
        {
            **{key: value for key, value in VALID_RULES_FILE.items() if key != "excluded_folders"},
            "exluded_folders": ["vendor"],
        },
    ],
    ids=["brak klucza", "klucz nieznany", "literówka w nazwie klucza"],
)
def test_rules_with_a_wrong_set_of_keys_are_rejected(
    tmp_path:   Path,
    rules_file: dict[str, list[str] | str],
) -> None:
    """Sprawdza, czy plik reguł, w którym brakuje klucza, jest klucz nieznany albo nazwa klucza
    ma literówkę, jest odrzucany błędem przy wczytaniu.

    Wyłapuje reguły z literówką przyjęte bez błędu: wyłączenie zapisane pod złą nazwą nie
    działałoby, a paczka powstałaby z wyłączonymi katalogami w środku."""
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules_file), encoding="utf-8")

    with pytest.raises(ValueError, match="klucze"):
        load_rules(path)


def test_rules_with_the_expected_keys_are_loaded(tmp_path: Path) -> None:
    """Sprawdza, czy plik reguł z kompletem oczekiwanych kluczy wczytuje się do obiektu reguł
    z tymi samymi wpisami.

    Wyłapuje wczytanie, które myli klucze ze sobą: wyłączenia trafiłyby na listę folderów do
    skopiowania albo odwrotnie."""
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(VALID_RULES_FILE), encoding="utf-8")

    rules = load_rules(path)

    assert rules == Rules(
        extensions       = ("php",),
        folders          = ("src/lib",),
        files            = (),
        excluded_folders = ("vendor",),
        excluded_files   = (),
    )
