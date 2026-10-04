import pytest
from pydantic import ValidationError

from app.core_model.gate_verdict import Verdict


def test_a_pass_needs_no_explanation() -> None:
    """`pass` bez uzasadnienia i wskazówki → poprawny: przepuszczenie nie wymaga tłumaczenia."""
    assert Verdict(verdict="pass").reasons == []


@pytest.mark.parametrize(
    "fields",
    [
        {"hint": "Dopisz, co zmieniono."},
        {"reasons": ["Nie widać zmian."]},
        {"reasons": ["Nie widać zmian."], "hint": "   "},
    ],
    ids=["no-reasons", "no-hint", "blank-hint"],
)
def test_a_block_without_reasons_or_hint_is_rejected(fields: dict[str, object]) -> None:
    """`block` bez uzasadnienia albo bez wskazówki → błąd walidacji: samo „nie" łamie zasadę 10."""
    with pytest.raises(ValidationError):
        Verdict(verdict="block", **fields)


def test_a_block_with_reasons_and_hint_is_accepted() -> None:
    """`block` z uzasadnieniem i wskazówką → poprawny; `missing` może zostać puste."""
    verdict = Verdict(verdict="block", reasons=["Nie widać zmian."], hint="Dopisz, co zmieniono.")

    assert verdict.missing == []


def test_an_unknown_key_is_an_error() -> None:
    """Klucz spoza kontraktu w odpowiedzi modelu → błąd walidacji, nie ciche odrzucenie."""
    with pytest.raises(ValidationError):
        Verdict.model_validate({"verdict": "pass", "confidence": 0.9})
