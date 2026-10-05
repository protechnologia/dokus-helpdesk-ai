from fastapi.testclient import TestClient

from app.agent_graphs import search
from app.agent_graphs.factory import get_graph_builder
from app.agent_graphs.fake import (
    FAKE_MAX_ITERATIONS,
    FAKE_READ_ARGUMENTS,
    FAKE_SEARCH_ARGUMENTS,
    fake_search_nodes,
)
from app.agent_nodes.agent import FakeAgentNode, tool_call_turn
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.agent_nodes.run_tools import RunToolsNode
from app.agent_tools import AgentTool
from app.agent_tools.tickets.find_tickets_vector.fake import FakeFindTicketsVectorTool
from app.config import Settings
from app.engine_anonymization import FakeAnonymizer
from app.engine_llm import LLMUsage
from app.main import create_app
from tests.helpers_agent_tools import find_tickets_vector_with_dead_embedder

# Kontrakt HTTP `POST /search` w procesie: kształt odpowiedzi (źródła + zapytania agenta),
# walidacja żądania i to, co trasa wkłada do grafu. Że trasa jest zamontowana w obrazie, sprawdza
# `stack_api`.

TICKET = {"ticket_id": "41002", "body": "Od wczoraj nie przychodzą przesyłki z e-Doręczeń."}

# Limity wywołań narzędzi, jakie daje konfiguracja domyślna.
LIMITS = Settings(_env_file=None).tool_call_limits()


def client_searching_with(
    tool: AgentTool,  # np. FakeFindTicketsVectorTool(tickets=[], dropped_below_threshold=3)
) -> TestClient:
    """
    Description:
    Aplikacja, w której graf `search` wykonuje narzędzia naprawdę: węzeł właściwy `run_tools`
    woła podane wyszukiwanie, a atrapa agenta szuka raz i kończy. Atrapa grafu z fabryki podaje
    wyniki narzędzi na sztywno, więc nie odtworzy ani progu, który wszystko wyciął, ani awarii.

    Example args:
        tool=FakeFindTicketsVectorTool(tickets=[], dropped_below_threshold=3)

    Example result:
        TestClient, którego `/search` szuka podanym narzędziem
    """
    graph = search.build_graph(
        anonymize      = AnonymizeNode(FakeAnonymizer()),
        agent          = FakeAgentNode([
            tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
            tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_2"),
        ]),
        run_tools      = RunToolsNode([tool], LIMITS),
        respond        = FakeRespondNode(search.SearchDone()),
        max_iterations = FAKE_MAX_ITERATIONS,
    )

    app = create_app()
    app.dependency_overrides[get_graph_builder] = lambda: (lambda module: graph)

    return TestClient(app)


def test_sources_and_agent_queries_go_out() -> None:
    """Sprawdza, czy `POST /search` oddaje źródła i zapytania agenta z przebiegu grafu: trzy
    przeczytane zgłoszenia (90001, 90002, 90003) oraz dwa wywołania narzędzi z argumentami,
    wyszukanie i odczyt kart. Wyszukanie niesie licznik trafień odciętych progiem (tu zero),
    a odczyt, który progu nie ma, puste pole. Wywołania narzędzia odpowiedzi na tej liście nie
    ma, bo ono niczego nie szuka.

    Wyłapuje trasę, która gubi źródła albo zapytania, lub dopisuje do zapytań wywołanie
    odpowiedzi: wołający nie widziałby, na czym stoi wynik ani o co agent pytał."""
    response = TestClient(create_app()).post("/search", json=TICKET)

    assert response.status_code == 200
    assert [item["item_id"] for item in response.json()["sources"]] == ["90001", "90002", "90003"]
    assert response.json()["queries"] == [
        {
            "tool":                    "find_tickets_vector",
            "arguments":               FAKE_SEARCH_ARGUMENTS,
            "dropped_below_threshold": 0,
        },
        {
            "tool":                    "read_tickets_card",
            "arguments":               FAKE_READ_ARGUMENTS,
            "dropped_below_threshold": None,
        },
    ]


def test_hits_cut_by_the_threshold_are_counted_in_the_response() -> None:
    """Sprawdza, czy `/search` odróżnia „próg wszystko wyciął" od „nic nie było": gdy wyszukiwanie
    nie oddało żadnego zgłoszenia, a trzy trafienia odpadły jako za słabe, odpowiedź ma status
    200, pustą listę źródeł i licznik 3 przy tym wyszukaniu.

    Wyłapuje odpowiedź, w której licznik odciętych trafień ginie po drodze: za ostry próg
    wyglądałby dla wołającego dokładnie tak samo jak pusty indeks."""
    tool     = FakeFindTicketsVectorTool(tickets=[], dropped_below_threshold=3)
    response = client_searching_with(tool).post("/search", json=TICKET)

    assert response.status_code       == 200
    assert response.json()["sources"] == []
    assert response.json()["queries"] == [
        {
            "tool":                    "find_tickets_vector",
            "arguments":               FAKE_SEARCH_ARGUMENTS,
            "dropped_below_threshold": 3,
        },
    ]


def test_a_dead_embedder_behind_a_tool_is_service_unavailable() -> None:
    """Sprawdza, czy awaria embeddera w narzędziu wyszukiwania kończy `POST /search` statusem 503
    we wspólnym kształcie błędu, z opisem wskazującym embedder.

    Wyłapuje awarię zależności narzędzia oddaną jako zwykły błąd serwera albo jako pusta lista
    źródeł: wołający nie odróżniłby wtedy „usługa chwilowo nie działa" od „nic nie znaleziono"."""
    client   = client_searching_with(find_tickets_vector_with_dead_embedder())
    response = client.post("/search", json=TICKET)

    assert response.status_code      == 503
    assert response.json()["detail"] == "Embedding service call failed"
    assert "request_id" in response.json()


def test_the_response_carries_the_model_usage_of_the_run() -> None:
    """Sprawdza, czy odpowiedź `/search` niesie zużycie modelu z całego przebiegu: trzy wywołania
    (szukaj, czytaj, odpowiedz), a przy atrapie modelu zero tokenów każdego rodzaju i zerowy
    koszt.

    Wyłapuje odpowiedź bez zużycia albo z licznikiem tylko jednej tury: wołający ma widzieć
    koszt całej sprawy bez sięgania do logów."""
    response = TestClient(create_app()).post("/search", json=TICKET)

    assert response.json()["usage"] == {
        "llm_calls":          3,
        "prompt_tokens":      0,
        "completion_tokens":  0,
        "cache_write_tokens": 0,
        "cache_read_tokens":  0,
        "cost_usd":           0.0,
    }


def test_the_response_carries_the_log_of_the_run() -> None:
    """Sprawdza, czy odpowiedź `/search` niesie log przebiegu grafu, po jednym wpisie na każdy
    krok i w kolejności wykonania: anonimizacja, dwie tury modelu z narzędziami (wyszukanie,
    potem odczyt kart) i tura z odpowiedzią. Wpisy tych dwóch tur nazywają wywołane narzędzie.

    Wyłapuje log, który ginie po drodze, ma pomieszaną kolejność albo nie mówi, które narzędzie
    wywołano: wołający ma widzieć przebieg sprawy bez sięgania do logów usługi."""
    log = TestClient(create_app()).post("/search", json=TICKET).json()["log"]

    assert [entry["node"] for entry in log] == [
        "anonymize",
        "agent", "run_tools",
        "agent", "run_tools",
        "agent", "respond",
    ]
    assert "find_tickets_vector" in log[1]["message"]
    assert "read_tickets_card"   in log[3]["message"]


def test_the_log_carries_no_ticket_text() -> None:
    """Sprawdza, czy log w odpowiedzi `/search` nie zawiera treści zgłoszenia: każdy wpis ma tylko
    pola `node` i `message`, a w `message` nie ma ani całego opisu z żądania, ani jego fragmentu
    (słowa „przesyłki").

    Wyłapuje przeciek danych klienta przez log przebiegu: log wraca w każdej odpowiedzi, więc ma
    nieść same nazwy, liczby i identyfikatory."""
    log = TestClient(create_app()).post("/search", json=TICKET).json()["log"]

    for entry in log:
        assert set(entry) == {"node", "message"}
        assert TICKET["body"] not in entry["message"]
        assert "przesyłki"    not in entry["message"]


def test_the_cost_of_the_run_goes_out_rounded() -> None:
    """Sprawdza, czy koszt przebiegu wraca w odpowiedzi `/search` zaokrąglony: po trzech turach
    modelu po 0,002 USD odpowiedź podaje trzy wywołania, 300 tokenów wejścia i koszt równo 0,006.

    Wyłapuje koszt oddany wprost z sumowania ułamków, z ogonem w rodzaju 0,006000000000000001,
    oraz zużycie, które nie sumuje się z kolejnych tur."""
    agent, run_tools = fake_search_nodes(search.RESPOND_TOOL_NAME, search.SearchDone())
    agent._usage     = LLMUsage(calls=1, prompt_tokens=100, completion_tokens=10, cost_usd=0.002)
    graph            = search.build_graph(
        AnonymizeNode(FakeAnonymizer()),
        agent,
        run_tools,
        FakeRespondNode(search.SearchDone()),
        FAKE_MAX_ITERATIONS,
    )

    app = create_app()
    app.dependency_overrides[get_graph_builder] = lambda: (lambda module: graph)

    usage = TestClient(app).post("/search", json=TICKET).json()["usage"]

    assert usage["llm_calls"]     == 3
    assert usage["prompt_tokens"] == 300
    assert usage["cost_usd"]      == 0.006


def test_a_source_carries_no_score() -> None:
    """Sprawdza, czy źródło w odpowiedzi `/search` ma dokładnie cztery pola: materiał (`source`),
    identyfikator (`item_id`), tytuł i datę, bez liczby podobieństwa.

    Wyłapuje powrót pola `score` albo innego pola wewnętrznego do odpowiedzi: źródłem jest to, co
    agent odczytał po numerze, a taki odczyt podobieństwa nie zna."""
    response = TestClient(create_app()).post("/search", json=TICKET)

    assert set(response.json()["sources"][0]) == {"source", "item_id", "title", "date"}


def test_the_graph_reads_the_whole_thread() -> None:
    """Sprawdza, czy `/search` podaje grafowi cały wątek zgłoszenia: tekst, który trafia do
    anonimizacji, zaczyna się od nagłówka „ZGŁOSZENIE 41002" i zawiera opis z żądania, czyli ma
    ten sam układ, w jakim zgłoszenia czyta parser korpusu.

    Wyłapuje trasę, która przekazuje sam opis albo gubi numer zgłoszenia: agent szukałby wtedy
    na podstawie innego tekstu niż ten, z jakiego powstały karty w indeksie."""
    anonymizer       = FakeAnonymizer()
    agent, run_tools = fake_search_nodes(search.RESPOND_TOOL_NAME, search.SearchDone())
    graph            = search.build_graph(
        AnonymizeNode(anonymizer),
        agent,
        run_tools,
        FakeRespondNode(search.SearchDone()),
        FAKE_MAX_ITERATIONS,
    )

    app = create_app()
    app.dependency_overrides[get_graph_builder] = lambda: (lambda module: graph)

    TestClient(app).post("/search", json=TICKET)

    assert anonymizer.texts[0].startswith("ZGŁOSZENIE 41002")
    assert "Od wczoraj nie przychodzą przesyłki" in anonymizer.texts[0]


def test_a_ticket_without_body_is_refused() -> None:
    """Sprawdza, czy `POST /search` bez opisu zgłoszenia (pola `body`) dostaje status 422.

    Wyłapuje trasę, która przyjmuje zgłoszenie bez treści i uruchamia graf: wyszukiwanie ruszyłoby
    bez opisu problemu, a wołający nie dowiedziałby się, że jego żądanie było niepełne."""
    response = TestClient(create_app()).post("/search", json={"ticket_id": "41002"})

    assert response.status_code == 422
