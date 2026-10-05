import pytest
from fastapi.testclient import TestClient

from app.agent_graphs.factory import build_real_graph, get_graph_builder
from app.agent_graphs.fake import FAKE_MAX_ITERATIONS
from app.agent_graphs.registry import variant_graphs
from app.agent_nodes.agent import tool_call_turn
from app.config import Settings
from app.engine_anonymization import FakeAnonymizer
from app.engine_llm import FakeLLMClient
from app.main import create_app
from tests.helpers_agent_tools import fake_agent_tools

# Kontrakt HTTP `/suggest` i `/variants`. Testy idą po rejestrze grafów, nie po zaszytej trójce
# wariantów (CLAUDE.md -> „Testy") — nowy katalog `suggest_*` jest objęty bez dopisywania.

VARIANTS = variant_graphs()

TICKET = {"ticket_id": "41002", "body": "Od wczoraj nie przychodzą przesyłki z e-Doręczeń."}

# Limity wywołań narzędzi, jakie daje konfiguracja domyślna.
LIMITS = Settings(_env_file=None).tool_call_limits()


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


@pytest.mark.parametrize(
    "variant",
    sorted(name for name, graph in VARIANTS.items() if graph.REQUIRES_HITS),
)
def test_a_variant_that_requires_sources_gives_no_proposal_without_them(variant: str) -> None:
    """Sprawdza, czy wariant wymagający źródeł, w którym model odpowiada od razu, bez przeczytania
    czegokolwiek, wraca ze statusem 200, bez propozycji (`text` równe `null`) i z pustą listą
    źródeł, a log przebiegu kończy się wpisem o braku źródeł.

    Wyłapuje rozwiązanie napisane przez model „z głowy", które wyszłoby do wdrożeniowca jako
    oparte na bazie, oraz brak źródeł oddany jako błąd: dla sprawy bez podobnych zgłoszeń to
    poprawna odpowiedź, nie awaria."""
    graph    = VARIANTS[variant]
    answer   = tool_call_turn(graph.RESPOND_TOOL_NAME, {"text": "Proszę zrestartować usługę."})
    compiled = build_real_graph(
        graph          = graph,
        llm            = FakeLLMClient(turns=[answer]),
        anonymizer     = FakeAnonymizer(),
        tools          = fake_agent_tools(),
        limits         = LIMITS,
        max_iterations = FAKE_MAX_ITERATIONS,
    )

    app = create_app()
    app.dependency_overrides[get_graph_builder] = lambda: (lambda module: compiled)

    response = TestClient(app).post("/suggest", json={**TICKET, "variant": variant})
    body     = response.json()

    assert response.status_code == 200
    assert body["text"]    is None
    assert body["sources"] == []
    assert body["log"][-1]["node"] == "respond"
    assert "brak źródeł" in body["log"][-1]["message"]
