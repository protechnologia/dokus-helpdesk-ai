"""
Description:
Rozbiór oznaczeń linii golden setu kanału „Automat mailowy” (`tests/_helpers/golden_mail/`):
zakresy z pól `tickets-mail.json` na etykietę na linię i skrót tekstu pola. Na nich stoi
test spójności zestawu i pomiar normalizera maili, więc błąd tu dałby fałszywy wynik pomiaru.
"""

import pytest

from tests._helpers.golden_mail import field_digest, parse_ranges


def test_ranges_become_one_label_per_line() -> None:
    """Sprawdza, czy zakresy „1-2 tresc; 3 podpis; 4-6 kopia” dają sześć etykiet po kolei,
    a pusty napis (pole bez linii ze słowami) — żadnej.

    Wyłapuje zakres liczony bez ostatniej linii albo pojedynczą linię pominiętą: etykiety
    przesunęłyby się względem linii pola."""
    assert parse_ranges("1-2 tresc; 3 podpis; 4-6 kopia") == (
        "tresc", "tresc", "podpis", "kopia", "kopia", "kopia",
    )
    assert parse_ranges("") == ()


@pytest.mark.parametrize(
    "spec",
    ["1-2 tresc; 4 kopia", "1-3 tresc; 3 kopia", "2 tresc", "1-2 treść", "1-2"],
    ids=["dziura", "nakładanie", "start nie od 1", "nieznana etykieta", "bez etykiety"],
)
def test_broken_ranges_are_refused(spec: str) -> None:
    """Sprawdza, czy zakresy z dziurą, nakładające się, zaczynające się nie od 1, z nieznaną
    etykietą albo bez etykiety kończą się błędem.

    Wyłapuje rozbiór, który przyjmuje taki zapis: część linii zostałaby bez etykiety albo
    z dwiema, a pomiar nie dałby tego poznać."""
    with pytest.raises(ValueError):
        parse_ranges(spec)


def test_the_field_digest_keeps_its_golden_value() -> None:
    """Sprawdza, czy skrót tekstu pola ma zapisaną wartość dla znanego tekstu i czy zmiana
    jednego znaku go zmienia.

    Wyłapuje zmianę sposobu liczenia skrótu: każde pole golden setu przestałoby się zgadzać
    z zapisanym skrótem, a test spójności padałby bez zmiany danych."""
    text = "Dzień dobry,\nod wczoraj nie możemy wysłać pisma."

    assert field_digest(text) == "ad7c2f36723bdde1"
    assert field_digest(text + " ") != field_digest(text)
