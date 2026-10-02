from datetime import date

from langgraph.graph.state import CompiledStateGraph

from app.anonymization import FakeAnonymizer
from app.graph.parse_ticket.graph import build_graph
from app.graph.parse_ticket.respond_tool import FILLED_BY_GRAPH, RESPOND_TOOL_NAME
from app.graph.parse_ticket.state import ParseTicketState
from app.model.ticket_parsed import ParsedTicket
from app.nodes.agent import FakeAgent, tool_call_turn
from app.nodes.anonymize import AnonymizeNode
from app.nodes.respond import FakeRespond
from app.service.loader_dict_resolution import get_resolution_classes


def default_ticket() -> ParsedTicket:
    """
    Description:
    Karta atrapy, gdy nikt nie podał własnej — zmyślona, nie skopiowana z korpusu (PII).

    Example args:
        (brak)

    Example result:
        ParsedTicket(ticket_id="90101", component="e-Doręczenia", problem="Nie przychodzą…", …)
    """
    ticket = ParsedTicket(
        ticket_id                     = "90101",
        date                          = date(2026, 9, 30),
        component                     = "e-Doręczenia",
        problem                       = "Nie przychodzą przesyłki z e-Doręczeń",
        symptoms                      = "Brak nowych przesyłek w skrzynce od wczoraj",
        error_codes                   = [],
        cause                         = "Zacięta kolejka pobierania po przerwanym połączeniu",
        solution                      = "Zrestartowano kolejkę; zaległe przesyłki doszły same.",
        resolution                    = "naprawione",
        resolution_vocabulary_version = get_resolution_classes().version,
        questions_summary             = "pytano, od kiedy brak przesyłek",
    )

    return ticket


def example_state() -> ParseTicketState:
    """
    Description:
    Przykładowy stan wejściowy grafu — do testów i atrap tras. Wątek zmyślony, słownik wbudowany.

    Example args:
        (brak)

    Example result:
        ParseTicketState(input_text="ZGŁOSZENIE 90101\\nTemat: Brak przesyłek…", vocabulary=…)
    """
    state = ParseTicketState(
        input_text = (
            "ZGŁOSZENIE 90101\nTemat: Brak przesyłek z e-Doręczeń\n\n"
            "[klient] Od wczoraj nie przychodzą przesyłki.\n\n"
            "[konsultant] Zrestartowaliśmy kolejkę pobierania, przesyłki już spływają."
        ),
        ticket_id  = "90101",
        date       = date(2026, 9, 30),
        vocabulary = get_resolution_classes(),
    )

    return state


def build_fake_graph(
    ticket: ParsedTicket | None = None,  # np. ParsedTicket(ticket_id="90101", …)
) -> CompiledStateGraph:
    """
    Description:
    Ten sam graf co `build_graph`, złożony z atrap — do testów tras i CLI. Agent wywołuje
    `respond_parse_ticket` z polami karty bez `FILLED_BY_GRAPH`, a `respond` oddaje całą kartę.

    Graf jest jednorazowy: `FakeAgent` ma jedną turę. Na każde wywołanie buduj nowy.

    Example args:
        ticket=None

    Example result:
        CompiledStateGraph, który na dowolny wątek oddaje `output` = podaną kartę
    """
    ticket = ticket if ticket is not None else default_ticket()
    answer = tool_call_turn(
        RESPOND_TOOL_NAME,
        ticket.model_dump(mode="json", exclude=set(FILLED_BY_GRAPH)),
    )

    graph = build_graph(
        anonymize = AnonymizeNode(FakeAnonymizer()),
        agent     = FakeAgent([answer]),
        respond   = FakeRespond(ticket),
    )

    return graph
