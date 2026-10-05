import pytest
from fastapi.testclient import TestClient

from app.agent_graphs.registry import variant_graphs
from app.main import create_app

# Kontrakt HTTP `/suggest` i `/variants`. Testy idą po rejestrze grafów, nie po zaszytej trójce
# wariantów (CLAUDE.md -> „Testy") — nowy katalog `suggest_*` jest objęty bez dopisywania.

VARIANTS = variant_graphs()

TICKET = {"ticket_id": "41002", "body": "Od wczoraj nie przychodzą przesyłki z e-Doręczeń."}


def test_variants_list_the_registry() -> None:
    """Sprawdza, czy `GET /variants` wymienia każdy wariant propozycji z rejestru grafów,
    w kolejności alfabetycznej, z nazwą, etykietą guzika i informacją, czy wariant wymaga źródeł
    (`requires_hits`).

    Wyłapuje listę, która rozjeżdża się z rejestrem, bo brakuje w niej wariantu albo ma on inną
    etykietę: helpdesk rysuje guziki z tej odpowiedzi, więc pokazałby inne, niż usługa obsługuje."""
    response = TestClient(create_app()).get("/variants")

    assert response.status_code == 200
    assert response.json()["variants"] == [
        {"name": name, "label": graph.LABEL, "requires_hits": graph.REQUIRES_HITS}
        for name, graph in sorted(VARIANTS.items())
    ]


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_every_variant_answers_in_one_shape(variant: str) -> None:
    """Sprawdza, czy `POST /suggest` odpowiada w tym samym kształcie dla każdego wariantu
    z rejestru: status 200, nazwa wariantu, niepusty tekst propozycji i log przebiegu od
    anonimizacji do odpowiedzi. Wariant z narzędziami wiedzy wraca ze źródłami, a wariant bez
    nich z pustą listą źródeł.

    Wyłapuje wariant, którego trasa nie obsługuje albo który odpowiada inaczej niż pozostałe:
    helpdesk musiałby wtedy pisać osobną obsługę odpowiedzi dla każdego guzika."""
    response = TestClient(create_app()).post("/suggest", json={**TICKET, "variant": variant})
    body     = response.json()

    assert response.status_code == 200
    assert body["variant"] == variant
    assert body["text"]
    assert bool(body["sources"]) == bool(VARIANTS[variant].TOOL_NAMES)
    assert body["log"][0]["node"]  == "anonymize"
    assert body["log"][-1]["node"] == "respond"


def test_an_unknown_variant_is_refused() -> None:
    """Sprawdza, czy `POST /suggest` z nieznanym wariantem (tu literówka „solutoin") dostaje status
    422, a opis błędu nazywa przysłany wariant.

    Wyłapuje ciche przejście na wariant domyślny: literówka w nazwie guzika po stronie helpdesku
    ma być widoczna od razu, a nie skończyć się inną propozycją, niż użytkownik kliknął."""
    response = TestClient(create_app()).post("/suggest", json={**TICKET, "variant": "solutoin"})

    assert response.status_code == 422
    assert "solutoin" in response.json()["detail"]
