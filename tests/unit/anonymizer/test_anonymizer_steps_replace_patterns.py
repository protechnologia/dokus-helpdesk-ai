import pkgutil

import pytest

import anonymizer_app.patterns
from anonymizer_app.steps.replace_patterns import (
    PATTERNS,
    VARIANTS,
    find_patterns,
    replace_patterns,
)
from tests._helpers.golden_anonymization import REMOVE_KINDS
from tests._helpers.patterns import PATTERN_KINDS

# Tekst z danymi każdego rodzaju od wzorców, na którym każdy wariant coś znajduje.
EVERY_KIND = (
    "PESEL 85030512843, 92112304576, NIP 742-136-51-80, REGON 431025874 i 43102587400016, "
    "konto PL30116022020000000312458701, dowód CBF248213, paszport EA0417295, tel. 600 100 200, "
    "81 532 10 15, tel. 6013, mail jan@ug.pl albo jan (at) ug.pl, AE:PL-12345-67890-ABCDE-12, "
    "ul. Lipowa 2, 21-100 Lubin, "
    "ul. Leśna 9, Toruń, al. Róż 3/5 w Opolu, ul. Polnej 15 i\n26-600 Radom"
)


def test_every_pattern_file_is_in_the_replacement() -> None:
    """Sprawdza, czy każdy plik wzorca z `patterns/` stoi w `PATTERNS` zamiany, a każdy wariant
    z jego `VARIANTS` jest funkcją z tego pliku.

    Wyłapuje nowy wzorzec, którego nikt nie dopisał do zamiany: jego testy przechodzą, a dane
    tego rodzaju i tak idą do modelu zewnętrznego."""
    files = {module.name for module in pkgutil.iter_modules(anonymizer_app.patterns.__path__)}

    assert {pattern.__name__.rsplit(".", 1)[-1] for pattern in PATTERNS} == files
    assert all(
        variant.__module__ == pattern.__name__
        for pattern in PATTERNS
        for variant in pattern.VARIANTS
    )


def test_every_pattern_has_a_golden_set_kind_and_finds_only_it() -> None:
    """Sprawdza, czy rodzaje wzorców to dokładnie rodzaje golden setu poza osobami i czy każdy
    wariant zwraca miejsca tylko rodzaju swojego pliku, a każdy coś znajduje w tekście z danymi
    wszystkich rodzajów.

    Wyłapuje literówkę w rodzaju, przez którą znacznik w wyniku i licznik w pomiarze golden setu
    rozjechałyby się z resztą, oraz wariant, który po zmianie wyrażenia nie łapie już niczego."""
    assert {pattern.KIND for pattern in PATTERNS} == set(PATTERN_KINDS) <= set(REMOVE_KINDS)

    for pattern in PATTERNS:
        for variant in pattern.VARIANTS:
            found = variant(EVERY_KIND)

            assert found, variant.__name__
            assert {place.kind for place in found} == {pattern.KIND}, variant.__name__


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("ul. Lipowa 2, 21-100 Lubin", "ul. {ADRES}", id="adres-z-kodem-zamiast-ulicy"),
        pytest.param("(22) 456 78 90 wew. 115", "{TELEFON}", id="numer-z-wewnetrznym"),
        pytest.param("ul. Leśna 9, Toruń", "ul. {ADRES}", id="ulica-z-miejscowoscia"),
    ],
)
def test_the_longest_place_wins_over_the_places_inside_it(text: str, expected: str) -> None:
    """Sprawdza, czy z miejsc, które na siebie zachodzą, zamiana bierze najdłuższe: adres z kodem
    zamiast samej ulicy, numer stacjonarny z wewnętrznym zamiast samego wewnętrznego.

    Wyłapuje zamianę, która bierze krótsze miejsce i zostawia w tekście resztę danej, na przykład
    kod pocztowy z miejscowością obok znacznika ulicy."""
    assert replace_patterns(text) == expected


def test_a_tie_goes_to_the_pattern_with_a_checksum() -> None:
    """Sprawdza, czy dziewięć cyfr z poprawną sumą REGON-u, które mają też kształt telefonu,
    dostaje znacznik `{REGON}`, a jedenaście cyfr złapanych przez dwa warianty PESEL-u daje jeden
    znacznik.

    Wyłapuje kolejność wzorców, w której telefon wygrywa z sumą kontrolną, i zamianę tego samego
    miejsca dwa razy, która psuje tekst."""
    assert replace_patterns("REGON 431025874") == "REGON {REGON}"
    assert replace_patterns("PESEL 92112304576") == "PESEL {PESEL}"


def test_the_replacement_changes_only_the_data() -> None:
    """Sprawdza, czy zamiana w zdaniu z kilkoma danymi zamienia każdą na znacznik jej rodzaju,
    a reszty, także imienia, którego wzorce nie łapią, nie rusza; to przykład z docstringu
    zamiany.

    Wyłapuje zamianę, która przesuwa miejsca po pierwszym znaczniku albo zjada sąsiednie słowa."""
    text = "Pani Barbara, PESEL 85030512840, tel. 600 100 200, ul. Lipowa 12/4, 21-100 Lubartów"

    assert replace_patterns(text) == "Pani Barbara, PESEL {PESEL}, tel. {TELEFON}, ul. {ADRES}"


def test_a_text_without_data_stays_unchanged_and_has_no_places() -> None:
    """Sprawdza, czy tekst bez danych o stałym kształcie, choć pełen liczb, wersji, kodów błędów
    i komunikatów, wychodzi z zamiany bez zmian, a `find_patterns()` nie zwraca żadnego miejsca.

    Wyłapuje wzorzec, który bierze za daną wersję, kod błędu albo liczbę z jednostką."""
    text = (
        "Po aktualizacji do wersji 2026.06.1 operator odrzuca pliki z komunikatem „Nieprawidłowe "
        "marginesy dokumentu”. W logu: java.lang.OutOfMemoryError, ORA-00942, SQLSTATE[23505]. "
        "Limit to 15 MB, marginesy 10/8/15 mm, port 8443, paczka 1180-2026, zgłoszenie 90116."
    )

    assert find_patterns(text) == []
    assert replace_patterns(text) == text


def test_the_variants_follow_the_order_of_the_patterns() -> None:
    """Sprawdza, czy `VARIANTS` to warianty wszystkich wzorców w kolejności `PATTERNS`.

    Wyłapuje listę wariantów sklejoną inaczej niż kolejność wzorców: remis dwóch miejsc tej
    samej długości rozstrzygałby się wtedy inaczej, niż mówi dokumentacja zamiany."""
    assert VARIANTS == tuple(variant for pattern in PATTERNS for variant in pattern.VARIANTS)
