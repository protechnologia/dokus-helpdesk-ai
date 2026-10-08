"""
Description:
Test integracyjny skryptu paczki kodu (`scripts/build_code_package.py`) na aplikacji
syntetycznej: paczka powstaje raz, w katalogu tymczasowym, ze źródła `data/safe/code/source/`
według reguł `data/safe/code/rules.json`. Bez stacku i bez modelu.

| co leży w źródle celowo                           | czego pilnuje test                        |
|---------------------------------------------------|-------------------------------------------|
| cache, pliki z hasłami, biblioteki, plik `.min`   | żaden nie wchodzi do paczki               |
| pliki wskazane wprost, poza folderami z listy     | wchodzą: źródło to paczka plus lista      |
| trzy komunikaty zapisane sekwencjami w plikach JS | są rozkodowane, a linie stoją w miejscu   |

O czym pamiętać przy zmianach:

- Listę plików, które nie mogą wejść do paczki, trzyma zestaw (`absent_paths`
  w `data/safe/golden/code-synthetic.json`). Nowy plik źródła, który ma nie wejść, dopisuje się
  tam; inaczej pada test „źródło to paczka plus lista".
- Test nie czyta ani nie zmienia paczki zbudowanej obok źródła (`data/safe/code/repo/`), na
  której stoją testy narzędzi kodu.
"""

import dataclasses
import json
from collections import Counter
from pathlib import Path
from typing import NamedTuple

import pytest
from build_code_package import CODE_DIR, MANIFEST_NAME, Manifest, build_package, load_rules

from tests.helpers_code_package import (
    SYNTHETIC_RULES_FILE,
    SYNTHETIC_SOURCE_DIR,
    synthetic_absent_paths,
)

ABSENT = synthetic_absent_paths()

# Początek sekwencji znaku w pliku JS: ukośnik i `u`.
ESCAPE_START = "\\u"


class Built(NamedTuple):
    """Paczka zbudowana na potrzeby tego pliku testów."""

    package_dir: Path      # np. Path("/tmp/pytest-of-root/pytest-0/paczka0")
    manifest:    Manifest  # metryczka oddana przez skrypt


@pytest.fixture(scope="module")
def built(
    tmp_path_factory: pytest.TempPathFactory,
) -> Built:
    """
    Description:
    Buduje paczkę z aplikacji syntetycznej do katalogu tymczasowego, raz na cały plik testów:
    każdy test ogląda tę samą paczkę z innej strony.

    Example args:
        tmp_path_factory=<fabryka katalogów tymczasowych pytesta>

    Example result:
        Built(package_dir=Path("/tmp/pytest-of-root/pytest-0/paczka0"), manifest=Manifest(...))
    """
    package_dir = tmp_path_factory.mktemp("paczka")
    manifest    = build_package(SYNTHETIC_SOURCE_DIR, package_dir, load_rules(SYNTHETIC_RULES_FILE))

    return Built(package_dir=package_dir, manifest=manifest)


def _files_in(
    root: Path,  # np. Path("data/safe/code/source")
) -> set[str]:
    """
    Description:
    Zbiera ścieżki wszystkich plików w katalogu, liczone od tego katalogu.

    Example args:
        root=Path("data/safe/code/source")

    Example result:
        {"src/web/index.php", "src/web/js/_global/bledy.js", ...}
    """
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def test_the_absent_list_names_files_that_exist_in_the_source() -> None:
    """Sprawdza, czy lista plików, które nie mogą wejść do paczki, nie jest pusta i czy każda jej
    ścieżka wskazuje plik istniejący w źródle aplikacji syntetycznej.

    Wyłapuje listę, która rozjechała się ze źródłem po zmianie nazwy pliku: test niżej
    potwierdzałby wtedy nieobecność pliku, którego i tak nigdzie nie ma."""
    missing = [path for path in ABSENT if not (SYNTHETIC_SOURCE_DIR / path).is_file()]

    assert ABSENT and not missing


@pytest.mark.parametrize("path", ABSENT)
def test_a_file_from_the_absent_list_is_not_in_the_package(built: Built, path: str) -> None:
    """Sprawdza, czy pliku z listy — z katalogu cache, z hasłem, z biblioteki zewnętrznej albo
    zminifikowanego — nie ma w zbudowanej paczce.

    Wyłapuje reguły albo skrypt, które przepuszczają taki plik: kod z paczki idzie do modelu
    zewnętrznego bez anonimizacji, więc hasło z pliku konfiguracji wyszłoby razem z nim."""
    assert not (built.package_dir / CODE_DIR / path).exists()


def test_the_source_is_the_package_plus_the_absent_list(built: Built) -> None:
    """Sprawdza, czy każdy plik źródła jest albo w paczce, albo na liście plików, które nie mogą
    wejść, i nigdy w obu miejscach naraz.

    Wyłapuje plik, który po cichu wypadł z paczki (na przykład wskazany wprost, spoza folderów
    z listy), oraz nowy plik źródła, o którym nikt nie zdecydował, czy ma wejść."""
    source  = _files_in(SYNTHETIC_SOURCE_DIR)
    package = _files_in(built.package_dir / CODE_DIR)

    assert package | set(ABSENT) == source
    assert not package & set(ABSENT)


def test_polish_letters_in_js_files_are_decoded(built: Built) -> None:
    """Sprawdza, czy trzy komunikaty zapisane w źródle sekwencjami stoją w paczce polskimi
    literami i czy metryczka podaje trzy zmienione linie w dwóch plikach.

    Wyłapuje paczkę z nierozkodowanymi komunikatami: dosłowne szukanie komunikatu z ekranu
    pomijałoby linię w głównej obsłudze błędów."""
    js_dir = built.package_dir / CODE_DIR / "src/web/js/_global"
    bledy  = (js_dir / "bledy.js").read_text(encoding="utf-8")
    okna   = (js_dir / "okna.js").read_text(encoding="utf-8")

    assert "Sesja wygasła. Zaloguj się ponownie." in bledy
    assert "Nie udało się skomunikować z serwerem" in bledy
    assert "'Błąd'" in okna
    assert built.manifest.changes.escapes_lines == 3
    assert built.manifest.changes.escapes_files == 2


def test_no_line_moves_between_the_source_and_the_package(built: Built) -> None:
    """Sprawdza, czy każdy plik paczki ma tyle samo linii co w źródle, a linie bez sekwencji są
    w nim znak w znak takie same.

    Wyłapuje skrypt, który przy poprawianiu treści dodaje, gubi albo zmienia linie: numer linii
    z paczki przestałby wskazywać to samo miejsce co w kodzie aplikacji."""
    repo = built.package_dir / CODE_DIR

    for path in sorted(_files_in(repo)):
        source_lines  = (SYNTHETIC_SOURCE_DIR / path).read_text(encoding="utf-8").split("\n")
        package_lines = (repo / path).read_text(encoding="utf-8").split("\n")
        # Linia z sekwencją ma w paczce inną treść; porównujemy pozostałe, każdą na jej miejscu.
        moved = [
            number
            for number, source_line in enumerate(source_lines[:len(package_lines)], start=1)
            if ESCAPE_START not in source_line and package_lines[number - 1] != source_line
        ]

        assert len(package_lines) == len(source_lines), path
        assert not moved, path


def test_the_manifest_describes_what_is_on_disk(built: Built) -> None:
    """Sprawdza, czy metryczka zgadza się z paczką na dysku: liczbę plików, liczbę linii i podział
    na rozszerzenia test liczy sam i porównuje, lista pominiętych wymienia wyłącznie pliki,
    których w paczce nie ma, a plik `manifest.json` niesie to samo, co skrypt oddał.

    Wyłapuje metryczkę liczoną inaczej, niż paczka jest zapisywana: po niej sprawdza się ręcznie,
    co model dostaje, a czego nie, więc zła liczba ukryłaby brakujący albo nadmiarowy plik."""
    files = sorted(_files_in(built.package_dir / CODE_DIR))
    texts = [(built.package_dir / CODE_DIR / path).read_bytes().decode("utf-8") for path in files]
    # Ostatnia linia liczy się także bez znaku końca; w paczce nie ma pustych plików.
    lines         = sum(text.count("\n") + (0 if text.endswith("\n") else 1) for text in texts)
    by_extension  = Counter(path.rsplit(".", 1)[-1] for path in files)
    manifest_file = json.loads((built.package_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    package       = built.manifest.package
    skipped       = built.manifest.skipped

    assert package.files             == len(files)
    assert package.lines             == lines
    assert package.by_extension      == dict(by_extension)
    assert skipped.not_utf8          == []
    assert set(skipped.not_in_rules) <= set(ABSENT)
    assert manifest_file             == dataclasses.asdict(built.manifest)
