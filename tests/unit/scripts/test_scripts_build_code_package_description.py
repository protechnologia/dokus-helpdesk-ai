"""
Description:
Testy jednostkowe wyjmowania ścieżek z opisu projektu (`paths_of_description` ze
`scripts/build_code_package.py`). Skrypt paczki sprawdza po nich, czy opis zgadza się z paczką;
samo sprawdzenie na plikach mają testy integracyjne.
"""

from build_code_package import paths_of_description

ROOTS = {"src"}


def test_a_path_is_a_backticked_text_that_starts_at_the_package_root() -> None:
    """Sprawdza, czy z opisu wychodzą napisy w odwróconych apostrofach zaczynające się od
    katalogu głównego paczki, a nazwa funkcji, nazwa zdarzenia z ukośnikiem (`global/raiseError`)
    i ścieżka bez apostrofów zostają pominięte.

    Wyłapuje wyjmowanie, które bierze za ścieżkę każdy napis z ukośnikiem: sprawdzenie opisu
    zgłaszałoby brak „pliku" o nazwie zdarzenia i nikt by mu nie wierzył."""
    text = (
        "Backend w `src/lib/`, wejście `src/web/index.php`. Zdarzenie `global/raiseError` "
        "obsługuje `OBI.errorHandler`. Stare pliki leżały w src/stare/."
    )

    expected, absent = paths_of_description(text, ROOTS)

    assert expected == ["src/lib/", "src/web/index.php"]
    assert absent   == []


def test_paths_under_the_absent_heading_are_expected_to_be_missing() -> None:
    """Sprawdza, czy ścieżki stojące pod nagłówkiem „Czego w paczce nie ma" trafiają na osobną
    listę, bez względu na poziom nagłówka i wielkość liter, a następny nagłówek tę sekcję
    zamyka.

    Wyłapuje wyjmowanie, które wrzuca wszystkie ścieżki do jednej listy: skrypt zgłaszałby brak
    skryptów update, choć opis mówi właśnie, że ich w paczce nie ma."""
    text = "\n".join([
        "## Baza danych",
        "Schematy w `src/config/doctrine/`.",
        "### CZEGO W PACZCE NIE MA",
        "- skryptów (`src/data/update/`),",
        "- stylów (`src/web/css/`).",
        "## Interfejs",
        "Kod w `src/web/js/`.",
    ])

    expected, absent = paths_of_description(text, ROOTS)

    assert expected == ["src/config/doctrine/", "src/web/js/"]
    assert absent   == ["src/data/update/", "src/web/css/"]


def test_a_path_named_twice_is_listed_once() -> None:
    """Sprawdza, czy ścieżka wymieniona w opisie dwa razy stoi na liście raz, w miejscu
    pierwszego wystąpienia.

    Wyłapuje listę z powtórzeniami: brakująca ścieżka byłaby zgłaszana tyle razy, ile razy
    opis ją wymienia."""
    text = "Kod w `src/web/js/`.\nCzęść wspólna też w `src/web/js/`, a okna w `src/web/js/okna/`."

    expected, _ = paths_of_description(text, ROOTS)

    assert expected == ["src/web/js/", "src/web/js/okna/"]


def test_a_description_without_headings_has_no_absent_paths() -> None:
    """Sprawdza, czy w opisie bez nagłówków, jak dwuzdaniowy opis aplikacji syntetycznej, każda
    ścieżka jest ścieżką, która ma być w paczce, także gdy zdanie mówi „w paczce nie ma".

    Wyłapuje rozpoznawanie sekcji po słowach w zdaniu: sekcję wyznacza wyłącznie nagłówek,
    inaczej zwykłe zdanie odwracałoby sprawdzenie ścieżek stojących po nim."""
    text = "Kod w `src/lib/`; plików z hasłami w paczce nie ma, są tylko `src/config/doctrine/`."

    expected, absent = paths_of_description(text, ROOTS)

    assert expected == ["src/lib/", "src/config/doctrine/"]
    assert absent   == []
