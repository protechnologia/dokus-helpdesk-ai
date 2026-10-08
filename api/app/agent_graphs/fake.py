from collections.abc import Mapping

from pydantic import BaseModel

from app.agent_nodes.agent import FakeAgentNode, tool_call_turn
from app.agent_nodes.run_tools import FakeRunToolsNode, FakeToolAnswer
from app.agent_tools.base import result_as_json
from app.agent_tools.tickets.fake_tickets import default_cards
from app.agent_tools.tickets.find_tickets_vector.fake import default_found
from app.agent_tools.tickets.find_tickets_vector.models import FindTicketsVectorResult
from app.agent_tools.tickets.read_tickets_card.fake import FakeReadTicketsCardTool
from app.agent_tools.tickets.read_tickets_card.models import ReadTicketsCardResult

# Zapytanie, które atrapa agenta wysyła do `find_tickets_vector` — w kształcie korpusu, zmyślone.
FAKE_SEARCH_ARGUMENTS = {
    "problem":  "Nie przychodzą przesyłki z e-Doręczeń",
    "symptoms": "Brak nowych przesyłek w skrzynce, nadawcy potwierdzają wysyłkę",
}

# Numery, których karty atrapa agenta czyta potem przez `read_tickets_card` — wszystkie znalezione.
FAKE_READ_ARGUMENTS = {
    "ticket_ids": [found.ticket_id for found in default_found()],
}

# Limit tur modelu w atrapach grafów, gdy nikt nie podał własnego. Przebieg „szukaj, czytaj,
# odpowiedz" ma trzy tury i mieści się w nim z zapasem; trasy dostają limit z konfiguracji.
FAKE_MAX_ITERATIONS = 10


def fake_search_nodes(
    respond_tool_name: str,                              # np. "respond_search"
    output:            BaseModel,                        # np. Proposal(text="1. Od kiedy…", …)
    limits:            Mapping[str, int] | None = None,  # np. {"read_tickets_card": 3}
) -> tuple[FakeAgentNode, FakeRunToolsNode]:
    """
    Description: Atrapy agenta i narzędzi dla grafu z narzędziami wiedzy, w przebiegu „szukaj,
    czytaj, odpowiedz": agent szuka `find_tickets_vector`, czyta karty wszystkich znalezionych
    numerów przez `read_tickets_card`, a potem wywołuje narzędzie odpowiedzi z `output`
    w argumentach. `run_tools` odpowiada na wyszukiwanie samymi numerami, a na odczyt kartami
    (jeden objaw, trzy przyczyny) i ich źródłami — tym samym JSON-em i tym samym `cite()`, co
    atrapy narzędzi. Źródła pojawiają się więc dopiero po odczycie. `limits` to limity wywołań
    narzędzi z konfiguracji: atrapa `run_tools` egzekwuje je tak samo jak węzeł właściwy.

    Example args:
        respond_tool_name="respond_suggest_questions"
        output=Proposal(text="1. Od kiedy…", internal_notes="1: …")
        limits={"find_tickets_vector": 3, "read_tickets_card": 3}

    Example result:
        (FakeAgentNode z trzema turami, FakeRunToolsNode z trzema źródłami z odczytu kart)
    """
    # --- co oddaje wyszukiwanie: numery ---
    found = FindTicketsVectorResult(tickets=default_found())

    # --- co oddaje odczyt: karty znalezionych numerów ---
    reader = FakeReadTicketsCardTool()
    wanted = FAKE_READ_ARGUMENTS["ticket_ids"]
    read   = ReadTicketsCardResult(
        cards = [card for card in default_cards() if card.ticket_id in wanted],
    )

    agent = FakeAgentNode([
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
        tool_call_turn("read_tickets_card", FAKE_READ_ARGUMENTS, call_id="call_2"),
        tool_call_turn(respond_tool_name, output.model_dump(), call_id="call_3"),
    ])
    run_tools = FakeRunToolsNode(
        answers = {
            "find_tickets_vector": FakeToolAnswer(text=result_as_json(found)),
            "read_tickets_card":   FakeToolAnswer(
                text    = reader.render_for_model(read),
                sources = reader.cite(read),
            ),
        },
        limits  = limits,
    )

    return agent, run_tools
