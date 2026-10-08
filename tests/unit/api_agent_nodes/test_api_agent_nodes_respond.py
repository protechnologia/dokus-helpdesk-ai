import json
from typing import Annotated, Any

import pytest
from pydantic import BaseModel, ConfigDict, Field

from app.agent_graphs import GraphState, merge_sources
from app.agent_nodes.agent import tool_call_turn
from app.agent_nodes.respond import MAX_RETRIES, RespondError, RespondNode
from app.agent_nodes.run_tools import calls_over_limit
from app.agent_tools import SourceRef
from app.agent_tools.base import is_error_json
from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.proposal_notes import ProposalNotes
from app.core_model.graphs.verdict import Verdict
from app.engine_llm import ChatMessage, ToolCall

# Węzeł właściwy `respond` sam, bez grafu: dostaje stan z ostatnią turą modelu i oddaje zmianę
# stanu. Przejście przez graf — powrót do modelu po poprawce i koniec przebiegu — sprawdzają testy
# integracyjne węzła.

RESPOND_TOOL = "respond_gate_close"

# Fragment, który stoi tylko w argumentach modelu — nie może wyjść poza wiadomość dla modelu.
CLIENT_TEXT = "Kowalski z kancelarii"

PASS  = {"verdict": "pass"}
BLOCK = {
    "verdict": "block",
    "reasons": ["Nie widać, co zrobiono."],
    "hint":    "Dopisz, co zmieniono.",
}

# Blokada bez wskazówki: model `Verdict` ją odrzuca (zasada 10).
BLOCK_WITHOUT_HINT = {"verdict": "block", "reasons": [CLIENT_TEXT]}

SEARCH = ToolCall(call_id="call_7", name="find_tickets_vector", arguments={"problem": "x"})
READ   = ToolCall(call_id="call_8", name="read_tickets_card", arguments={"ticket_ids": ["90001"]})

# Propozycja w kształcie wariantu z rozwiązaniem: treść dla klienta i uwagi dla wdrożeniowca.
SOLUTION_TOOL = "respond_suggest_solution"
PROPOSAL      = {"text": "Prosimy o restart usługi.", "internal_notes": "Szukałem po komunikacie."}

# Źródło odczytane przez agenta — wystarczy jedno, żeby graf wymagający źródeł je miał.
CARD_REF = SourceRef(source="tickets", item_id="90001", title="Brak przesyłek")


class State(GraphState):
    """Stan grafu bez narzędzi wiedzy: same pola wspólne."""


class SourcesState(GraphState):
    """Stan grafu z narzędziami wiedzy: pola wspólne plus `sources`."""

    sources: Annotated[list[SourceRef], merge_sources] = Field(default_factory=list)


class Card(BaseModel):
    """Wynik grafu z polem, które wypełnia graf (`ticket_id`), i polem od modelu (`problem`)."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    problem:   str = Field(min_length=1)


def gate_node() -> RespondNode:
    """
    Description:
    Węzeł odpowiedzi w kształcie bramki: czyta `respond_gate_close` jako `Verdict`.

    Example args:
        (brak)

    Example result:
        RespondNode(respond_tool_name="respond_gate_close", output_model=Verdict)
    """
    return RespondNode(respond_tool_name=RESPOND_TOOL, output_model=Verdict)


def notes_only(
    proposal: Proposal,  # np. Proposal(text="Prosimy o restart usługi.", internal_notes="…")
) -> ProposalNotes:
    """
    Description:
    Funkcja grafu na sprawę bez źródeł: z propozycji zostają same uwagi.

    Example args:
        proposal=Proposal(text="Prosimy o restart usługi.", internal_notes="Szukałem…")

    Example result:
        ProposalNotes(internal_notes="Szukałem…")
    """
    return ProposalNotes(internal_notes=proposal.internal_notes)


def solution_node() -> RespondNode:
    """
    Description:
    Węzeł odpowiedzi w kształcie wariantu z rozwiązaniem: czyta `respond_suggest_solution` jako
    `Proposal`, wymaga źródeł, a bez nich zostawia same uwagi.

    Example args:
        (brak)

    Example result:
        RespondNode(respond_tool_name="respond_suggest_solution", output_model=Proposal, …)
    """
    node = RespondNode(
        respond_tool_name = SOLUTION_TOOL,
        output_model      = Proposal,
        requires_sources  = True,
        without_sources   = notes_only,
    )

    return node


def state_after(
    *messages: ChatMessage,  # rozmowa; ostatnia wiadomość to zwykle tura modelu
    retries:   int = 0,      # ile poprawek już było w tej sprawie
) -> State:
    """
    Description:
    Stan grafu bez narzędzi wiedzy po podanej rozmowie.

    Example args:
        messages=(tool_call_turn("respond_gate_close", {"verdict": "pass"}),)
        retries=0

    Example result:
        State(input_text="x", messages=[ChatMessage(role="assistant", …)], respond_retries=0)
    """
    return State(input_text="x", messages=list(messages), respond_retries=retries)


def answer(
    arguments: dict[str, Any],     # np. {"verdict": "pass"}
    call_id:   str = "call_1",     # np. "call_2"
    name:      str = RESPOND_TOOL,  # np. "respond_suggest_solution"
) -> ChatMessage:
    """
    Description:
    Tura modelu z jednym wywołaniem narzędzia odpowiedzi.

    Example args:
        arguments={"verdict": "pass"}

    Example result:
        ChatMessage(role="assistant", tool_calls=[ToolCall(name="respond_gate_close", …)])
    """
    return tool_call_turn(name, arguments, call_id=call_id)


async def test_a_valid_answer_becomes_the_output() -> None:
    """Sprawdza, czy poprawne wywołanie narzędzia odpowiedzi staje się wynikiem grafu: węzeł
    zapisuje werdykt w `output` i zostawia w dzienniku wpis z nazwą typu wyniku, a niczego nie
    odsyła modelowi.

    Wyłapuje węzeł, który gubi odpowiedź modelu albo odsyła do poprawki także poprawną: trasa
    nie miałaby wtedy czego oddać albo każda sprawa kosztowałaby dodatkową turę."""
    update = await gate_node().run(state_after(answer(BLOCK)))

    assert update["output"]         == Verdict(**BLOCK)
    assert update["log"][0].message == "output: Verdict"
    assert "messages"        not in update
    assert "respond_retries" not in update


async def test_invalid_arguments_go_back_to_the_model_as_a_tool_error() -> None:
    """Sprawdza, czy werdykt blokujący bez wskazówki nie zostaje wynikiem, tylko wraca do modelu:
    jako błąd w miejscu wyniku narzędzia, pod identyfikatorem tego wywołania, z nazwą narzędzia
    i z tym, co jest nie tak. Licznik poprawek rośnie do 1.

    Wyłapuje blokadę bez wskazówki, która przeszłaby do wołającego, oraz poprawkę, której model
    nie umiałby przypisać do swojego wywołania: dostawca odrzuca rozmowę z wywołaniem bez
    odpowiedzi."""
    update   = await gate_node().run(state_after(answer(BLOCK_WITHOUT_HINT, call_id="call_3")))
    feedback = update["messages"]

    assert "output" not in update
    assert [(message.role, message.call_id) for message in feedback] == [("tool", "call_3")]
    assert is_error_json(feedback[0].content)
    assert RESPOND_TOOL in json.loads(feedback[0].content)["error"]
    assert "hint"       in json.loads(feedback[0].content)["error"]
    assert update["respond_retries"] == 1


async def test_plain_text_goes_back_as_a_user_message() -> None:
    """Sprawdza, czy tura modelu z samym tekstem, bez wywołania narzędzia, wraca do poprawki jako
    zwykła wiadomość (rola `user`), która nazywa narzędzie odpowiedzi.

    Wyłapuje poprawkę wysłaną jako wynik narzędzia, którego nikt nie wywołał: dostawca odrzuciłby
    taką rozmowę, a to zwykły przypadek u modelu, którego nie da się zmusić do wywołania
    narzędzia."""
    text   = ChatMessage(role="assistant", content="Zgłoszenie można zamknąć.")
    update = await gate_node().run(state_after(text))

    assert "output" not in update
    assert [message.role for message in update["messages"]] == ["user"]
    assert RESPOND_TOOL in update["messages"][0].content
    assert update["log"][0].message == "do poprawki: tekst zamiast narzędzia"


async def test_an_answer_with_another_call_is_rejected_as_a_whole() -> None:
    """Sprawdza, czy odpowiedź wywołana w jednej turze razem z innym narzędziem nie zostaje
    wynikiem: oba wywołania dostają błąd pod własnymi identyfikatorami, także to poprawne.

    Wyłapuje przyjęcie odpowiedzi, przy której model chciał jeszcze czegoś szukać, oraz wywołanie
    zostawione bez odpowiedzi: dostawca odrzuca rozmowę, w której którekolwiek wywołanie nie ma
    wyniku."""
    turn   = ChatMessage(role="assistant", tool_calls=[SEARCH, *answer(PASS).tool_calls])
    update = await gate_node().run(state_after(turn))

    assert "output" not in update
    assert [message.call_id for message in update["messages"]] == ["call_7", "call_1"]
    assert all(is_error_json(message.content) for message in update["messages"])
    assert update["log"][0].message == "do poprawki: odpowiedź z innym wywołaniem"


async def test_knowledge_calls_without_an_answer_are_told_to_answer() -> None:
    """Sprawdza, czy tura z samymi narzędziami wiedzy, która trafiła do węzła odpowiedzi (sprawa
    wyczerpała limit tur), wraca do modelu: każde wywołanie dostaje błąd z informacją, że nie
    zostało wykonane i że trzeba odpowiedzieć narzędziem odpowiedzi.

    Wyłapuje sprawę uciętą limitem tur, która kończy się bez wyniku, choć model miał już
    przeczytany materiał i wystarczyła jedna tura na odpowiedź."""
    turn   = ChatMessage(role="assistant", tool_calls=[SEARCH, READ])
    update = await gate_node().run(state_after(turn))
    errors = [json.loads(message.content)["error"] for message in update["messages"]]

    assert [message.call_id for message in update["messages"]] == ["call_7", "call_8"]
    assert all("nie zostało wykonane" in error and RESPOND_TOOL in error for error in errors)
    assert update["log"][0].message == "do poprawki: brak wywołania odpowiedzi"


async def test_rejected_calls_do_not_use_up_tool_limits() -> None:
    """Sprawdza, czy wywołanie narzędzia wiedzy odrzucone przez węzeł odpowiedzi nie liczy się do
    limitu tego narzędzia: po odrzuconej turze model może wywołać je jeszcze raz przy limicie 1.

    Wyłapuje poprawkę, która po cichu zabiera modelowi wywołania, których nikt nie wykonał."""
    turn     = ChatMessage(role="assistant", tool_calls=[SEARCH])
    update   = await gate_node().run(state_after(turn))
    again    = tool_call_turn("find_tickets_vector", {"problem": "x"}, call_id="call_9")
    messages = [turn, *update["messages"], again]

    assert calls_over_limit(messages, {"find_tickets_vector": 1}) == set()


@pytest.mark.parametrize(
    "turn",
    [
        answer(BLOCK_WITHOUT_HINT),
        ChatMessage(role="assistant", content=CLIENT_TEXT),
        ChatMessage(role="assistant", tool_calls=[SEARCH]),
    ],
    ids=["błędne argumenty", "sam tekst", "inne narzędzie"],
)
async def test_a_second_invalid_answer_ends_the_run_with_an_error(turn: ChatMessage) -> None:
    """Sprawdza, czy druga odpowiedź nie do przyjęcia w tej samej sprawie kończy przebieg błędem
    `RespondError`, niezależnie od rodzaju błędu. Komunikat nazywa narzędzie odpowiedzi, ale nie
    cytuje tego, co model napisał.

    Wyłapuje pętlę poprawek bez końca, w której każda tura kosztuje, oraz treść odpowiedzi modelu
    w komunikacie błędu, który trafia do logów usługi."""
    with pytest.raises(RespondError) as raised:
        await gate_node().run(state_after(turn, retries=MAX_RETRIES))

    assert RESPOND_TOOL    in str(raised.value)
    assert CLIENT_TEXT not in str(raised.value)


async def test_the_log_names_the_kind_of_error_only() -> None:
    """Sprawdza, czy wpis w dzienniku przebiegu po odrzuconej odpowiedzi mówi tylko, jaki to był
    rodzaj błędu, i nie zawiera wartości argumentów podanych przez model.

    Wyłapuje przeciek danych klienta przez dziennik przebiegu: wraca on do wołającego w każdej
    odpowiedzi, a argumenty modelu powstają z treści zgłoszenia."""
    update = await gate_node().run(state_after(answer(BLOCK_WITHOUT_HINT)))

    assert update["log"][0].message == "do poprawki: błędne argumenty"
    assert CLIENT_TEXT not in update["log"][0].message


async def test_a_graph_that_requires_sources_gives_no_output_without_them() -> None:
    """Sprawdza, czy węzeł grafu wymagającego źródeł, który nie dostał od grafu funkcji na sprawę
    bez źródeł, kończy bez wyniku i bez poprawki, gdy agent żadnego źródła nie odczytał — także
    wtedy, gdy model oddał poprawną odpowiedź. W dzienniku zostaje wpis o braku źródeł.

    Wyłapuje propozycję rozwiązania napisaną „z głowy", która przeszłaby do wołającego, oraz
    poprawkę odsyłaną modelowi, choć nie on jest winien braku źródeł."""
    node   = RespondNode(RESPOND_TOOL, Verdict, requires_sources=True)
    state  = SourcesState(input_text="x", messages=[answer(BLOCK)])
    update = await node.run(state)

    assert set(update) == {"log"}
    assert "brak źródeł" in update["log"][0].message


async def test_a_graph_that_requires_sources_accepts_the_answer_when_it_has_them() -> None:
    """Sprawdza, czy węzeł grafu wymagającego źródeł przyjmuje odpowiedź, gdy w stanie jest choć
    jedno odczytane źródło.

    Wyłapuje wymóg źródeł, który blokuje każdą odpowiedź: wariant z rozwiązaniem nie oddawałby
    wtedy propozycji nigdy."""
    node   = RespondNode(RESPOND_TOOL, Verdict, requires_sources=True)
    state  = SourcesState(input_text="x", messages=[answer(PASS)], sources=[CARD_REF])
    update = await node.run(state)

    assert update["output"] == Verdict(verdict="pass")


async def test_without_sources_the_graph_function_decides_what_stays() -> None:
    """Sprawdza, czy węzeł grafu wymagającego źródeł, który dostał funkcję na sprawę bez źródeł,
    czyta odpowiedź modelu także wtedy, gdy źródeł nie ma, i zapisuje w wyniku to, co zostawi ta
    funkcja: z propozycji same uwagi, bez treści dla klienta. Dziennik mówi o braku źródeł i nazywa
    typ wyniku.

    Wyłapuje treść dla klienta napisaną „z głowy", która przeszłaby do wołającego, oraz uwagi
    zgubione razem z nią: wdrożeniowiec nie wiedziałby, czego agent szukał i co wykluczył."""
    state  = SourcesState(input_text="x", messages=[answer(PROPOSAL, name=SOLUTION_TOOL)])
    update = await solution_node().run(state)

    assert update["output"]         == ProposalNotes(internal_notes="Szukałem po komunikacie.")
    assert update["log"][0].message == "brak źródeł: output: ProposalNotes"


async def test_without_sources_an_invalid_answer_still_goes_back_to_the_model() -> None:
    """Sprawdza, czy w sprawie bez źródeł odpowiedź, której nie da się przyjąć (tu bez pola
    z uwagami), wraca do modelu do poprawki tak samo jak w każdej innej sprawie.

    Wyłapuje sprawę bez źródeł, która kończy się bez uwag albo błędem, choć model mógł jeszcze
    poprawić odpowiedź."""
    turn   = answer({"text": "Prosimy o restart usługi."}, name=SOLUTION_TOOL)
    update = await solution_node().run(SourcesState(input_text="x", messages=[turn]))

    assert "output" not in update
    assert update["respond_retries"] == 1


async def test_with_sources_the_graph_function_is_not_used() -> None:
    """Sprawdza, czy węzeł z funkcją na sprawę bez źródeł zapisuje całą propozycję, gdy agent
    odczytał choć jedno źródło.

    Wyłapuje funkcję wołaną zawsze: wariant z rozwiązaniem nie oddawałby wtedy treści dla klienta
    nigdy, także przy przeczytanych zgłoszeniach."""
    turn   = answer(PROPOSAL, name=SOLUTION_TOOL)
    state  = SourcesState(input_text="x", messages=[turn], sources=[CARD_REF])
    update = await solution_node().run(state)

    assert update["output"] == Proposal(**PROPOSAL)


def test_a_function_for_missing_sources_without_requiring_them_is_refused() -> None:
    """Sprawdza, czy węzła odpowiedzi nie da się zbudować z funkcją na sprawę bez źródeł, gdy graf
    źródeł nie wymaga.

    Wyłapuje źle złożony graf, w którym ta funkcja nie zadziałałaby nigdy, a autor grafu byłby
    przekonany, że treść bez źródeł jest odrzucana."""
    with pytest.raises(ValueError):
        RespondNode(
            respond_tool_name = SOLUTION_TOOL,
            output_model      = Proposal,
            without_sources   = notes_only,
        )


async def test_requiring_sources_without_the_field_is_a_build_error() -> None:
    """Sprawdza, czy węzeł wymagający źródeł, wpięty w graf, którego stan nie ma listy źródeł,
    kończy się błędem `ValueError`, zamiast uznać, że źródeł po prostu nie ma.

    Wyłapuje źle złożony graf: wariant wymagający źródeł bez narzędzi wiedzy nigdy nie oddałby
    propozycji i wyglądałoby to jak zwykły brak trafień."""
    node = RespondNode(RESPOND_TOOL, Verdict, requires_sources=True)

    with pytest.raises(ValueError):
        await node.run(state_after(answer(PASS)))


async def test_fields_filled_by_the_graph_win_over_the_model() -> None:
    """Sprawdza, czy pola, które wypełnia graf, trafiają do wyniku ze stanu: numer zgłoszenia
    pochodzi od grafu także wtedy, gdy model podał własny.

    Wyłapuje kartę zgłoszenia z numerem wymyślonym przez model albo odrzuconą, bo brakuje w niej
    pola, o które model nie był pytany."""
    node = RespondNode(
        respond_tool_name = "respond_parse_ticket",
        output_model      = Card,
        filled_by_graph   = lambda state: {"ticket_id": "90101"},
    )
    turn = answer({"ticket_id": "1", "problem": "Brak przesyłek"}, name="respond_parse_ticket")

    update = await node.run(state_after(turn))

    assert update["output"] == Card(ticket_id="90101", problem="Brak przesyłek")


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [answer(PASS), ChatMessage(role="tool", call_id="call_1", content="{}")],
    ],
    ids=["pusta rozmowa", "rozmowa kończy się wynikiem narzędzia"],
)
async def test_a_run_without_a_model_turn_is_a_build_error(messages: list[ChatMessage]) -> None:
    """Sprawdza, czy węzeł wywołany bez tury modelu na końcu rozmowy kończy się błędem
    `ValueError`.

    Wyłapuje źle złożony graf, w którym węzeł odpowiedzi stoi przed modelem albo zaraz po
    narzędziach: bez tego błędu odsyłałby do poprawki odpowiedź, której nikt nie dał."""
    with pytest.raises(ValueError):
        await gate_node().run(state_after(*messages))


def test_a_node_without_the_tool_name_is_refused() -> None:
    """Sprawdza, czy węzła odpowiedzi nie da się zbudować bez nazwy narzędzia odpowiedzi.

    Wyłapuje graf, w którym węzeł nie rozpoznałby żadnego wywołania jako odpowiedzi i odsyłał do
    poprawki każdą sprawę."""
    with pytest.raises(ValueError):
        RespondNode(respond_tool_name="", output_model=Verdict)
