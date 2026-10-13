import pytest
from pydantic import ValidationError

from app.core_model.code.code_symbol import CodeSymbol

# Wpis mapy symboli w kształcie, w jakim zapisuje go skrypt paczki.
METHOD = {
    "name":      "nastepnyNumer",
    "scope":     "GeneratorNumeru",
    "kind":      "method",
    "from_line": 13,
    "to_line":   26,
}


def test_a_symbol_keeps_its_name_place_kind_and_lines() -> None:
    """Sprawdza, czy wpis mapy symboli staje się modelem z tą samą nazwą, miejscem, rodzajem
    i numerami linii.

    Wyłapuje model, którego pola nazywają się inaczej niż w pliku mapy: każda mapa zapisana
    przez skrypt byłaby wtedy odrzucana przy odczycie."""
    symbol = CodeSymbol(**METHOD)

    assert symbol.model_dump() == METHOD


def test_the_place_may_be_empty_but_must_be_said() -> None:
    """Sprawdza, czy symbol przyjmuje miejsce równe `None` (klasa, funkcja poza klasą), ale
    odrzuca wpis bez pola `scope`.

    Wyłapuje model, w którym miejsce ma wartość domyślną: wpis metody zapisany bez tego pola
    wyglądałby jak funkcja poza klasą, choć skrypt po prostu go nie zapisał."""
    assert CodeSymbol(**{**METHOD, "kind": "class", "scope": None}).scope is None

    with pytest.raises(ValidationError):
        CodeSymbol(**{key: value for key, value in METHOD.items() if key != "scope"})


@pytest.mark.parametrize(
    "changed",
    [
        {"name": ""},
        {"scope": ""},
        {"kind": "namespace"},
        {"from_line": 0},
        {"to_line": -257},
        {"signature": "($rok)"},
    ],
    ids=["pusta nazwa", "puste miejsce", "zły rodzaj", "linia 0", "linia ujemna", "nieznane pole"],
)
def test_a_wrong_entry_of_the_map_is_refused(changed: dict) -> None:
    """Sprawdza, czy wpis z pustą nazwą, pustym miejscem, rodzajem spoza listy, numerem linii
    mniejszym niż 1 albo polem spoza modelu kończy się wyjątkiem `ValidationError`.

    Wyłapuje model, który przyjmuje uszkodzony wpis: błąd pamięci parsera dawał w mapie numery
    ujemne, a narzędzie próbowałoby oddać linie, których w pliku nie ma."""
    with pytest.raises(ValidationError):
        CodeSymbol(**{**METHOD, **changed})
