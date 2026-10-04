import pytest
from fastapi.testclient import TestClient

from app.agent_graphs.registry import variant_graphs
from app.main import create_app

# Kontrakt HTTP `/suggest` i `/variants`. Testy idą po rejestrze grafów, nie po zaszytej trójce
# wariantów (CLAUDE.md -> „Testy") — nowy katalog `suggest_*` jest objęty bez dopisywania.

VARIANTS = variant_graphs()

TICKET = {"ticket_id": "41002", "body": "Od wczoraj nie przychodzą przesyłki z e-Doręczeń."}


def test_variants_list_the_registry() -> None:
    """`GET /variants` → każdy graf `suggest_*` jako guzik: nazwa, etykieta, `requires_hits`."""
    response = TestClient(create_app()).get("/variants")

    assert response.status_code == 200
    assert response.json()["variants"] == [
        {"name": name, "label": graph.LABEL, "requires_hits": graph.REQUIRES_HITS}
        for name, graph in sorted(VARIANTS.items())
    ]


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_every_variant_answers_in_one_shape(variant: str) -> None:
    """Każdy wariant → ten sam kształt: wariant, tekst propozycji, źródła; wariant bez narzędzi
    wiedzy z pustą listą źródeł."""
    response = TestClient(create_app()).post("/suggest", json={**TICKET, "variant": variant})
    body     = response.json()

    assert response.status_code == 200
    assert body["variant"] == variant
    assert body["text"]
    assert bool(body["sources"]) == bool(VARIANTS[variant].TOOL_NAMES)


def test_an_unknown_variant_is_refused() -> None:
    """Nieznany wariant → 422 z listą dostępnych, nie cichy fallback na domyślny."""
    response = TestClient(create_app()).post("/suggest", json={**TICKET, "variant": "solutoin"})

    assert response.status_code == 422
    assert "solutoin" in response.json()["detail"]
