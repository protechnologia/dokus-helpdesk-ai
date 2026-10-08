"""
Description:
Węzeł `respond`: ostatni krok każdego grafu. Sprawdza, czy model odpowiedział narzędziem
`respond_<graf>` i czy argumenty tego wywołania są poprawnym wynikiem grafu, a potem zapisuje
wynik w stanie. Odpowiedź, której nie da się przyjąć, wraca do modelu do poprawki — jeden raz.

Przed — ostatnia tura modelu w bramce zamknięcia blokuje zgłoszenie, ale bez wskazówki:

    messages[-1] = ChatMessage(role="assistant", tool_calls=[
        ToolCall(call_id="call_1", name="respond_gate_close",
                 arguments={"verdict": "block", "reasons": ["Nie widać, co zrobiono."]}),
    ])

Po — zmiana stanu: werdykt nie przeszedł walidacji, więc model dostaje błąd w miejscu wyniku
narzędzia, a graf wraca do węzła `agent`:

    {
        "messages":        [ChatMessage(
            role    = "tool",
            call_id = "call_1",
            content = '{"error": "Błędne argumenty narzędzia `respond_gate_close`: rekord: Value '
                      'error, werdykt block musi nieść uzasadnienie (reasons) i wskazówkę (hint). '
                      'Popraw argumenty i wywołaj narzędzie ponownie."}',
        )],
        "respond_retries": 1,
        "log":             [LogEntry(node="respond", message="do poprawki: błędne argumenty")],
    }

Po poprawionej odpowiedzi ten sam węzeł zwraca już wynik:

    {
        "output": Verdict(verdict="block", reasons=["Nie widać, co zrobiono."], missing=[],
                          hint="Dopisz, co zmieniono."),
        "log":    [LogEntry(node="respond", message="output: Verdict")],
    }

Co węzeł robi z ostatnią turą modelu:

| co model oddał                                         | co robi węzeł                       |
|--------------------------------------------------------|-------------------------------------|
| samo wywołanie `respond_<graf>`, poprawne argumenty    | zapisuje wynik w `output`           |
| samo wywołanie `respond_<graf>`, błędne argumenty      | odsyła do poprawki                  |
| `respond_<graf>` razem z innym wywołaniem              | odsyła do poprawki                  |
| inne narzędzia bez odpowiedzi (ucięte limitem tur)     | odsyła do poprawki                  |
| sam tekst, bez wywołań                                 | odsyła do poprawki                  |
| cokolwiek, a graf wymaga źródeł i nie ma ani jednego   | kończy bez wyniku, bez poprawki     |

Graf, który wymaga źródeł, może podać funkcję `without_sources`. Wtedy bez źródeł węzeł czyta
odpowiedź tak jak zawsze, razem z poprawką, a w `output` zapisuje to, co z niej zostawi ta
funkcja. W `suggest_solution` zostają same uwagi dla wdrożeniowca, a treść dla klienta odpada.

Co się dzieje po drodze:

1. Graf, który wymaga źródeł (`requires_sources`), bez źródeł w stanie i bez funkcji
   `without_sources` kończy bez wyniku: `output` zostaje puste, a odpowiedzi modelu węzeł
   w ogóle nie czyta.
2. Ostatnia tura modelu musi być jednym wywołaniem narzędzia odpowiedzi.
3. Do argumentów od modelu dochodzą pola, które wypełnia graf (`filled_by_graph`), a całość
   waliduje model wyniku grafu.
4. Odpowiedź nie do przyjęcia wraca do modelu: każde wywołanie z tej tury dostaje wiadomość
   `tool` z błędem, a tura z samym tekstem — wiadomość `user`. Licznik `respond_retries`
   rośnie i graf prowadzi z powrotem do `agent` (`route_after_respond`).
5. Druga odpowiedź nie do przyjęcia w tej samej sprawie to `RespondError`: przebieg staje,
   a trasa oddaje 503.
6. Gdy źródeł nie ma, a graf podał funkcję `without_sources`, przyjęta odpowiedź przechodzi
   przez nią, zanim trafi do `output`.

O czym pamiętać przy zmianach:

- Poprawka jest jedna na sprawę, niezależnie od rodzaju błędu (`MAX_RETRIES`). Model, który dwa
  razy nie utrzymał formatu, za trzecim też go nie utrzyma, a każda tura kosztuje.
- Tura poprawki nie liczy się do limitu tur: sprawa ucięta limitem dostaje jeszcze jedną turę
  na samą odpowiedź, bo jest już opłacona. W tej turze narzędzia wiedzy nadal nie ruszają.
- Każde wywołanie z odrzuconej tury dostaje wiadomość `tool` ze swoim `call_id`: dostawca nie
  przyjmie rozmowy z wywołaniem bez odpowiedzi. Te wiadomości to błędy (`{"error": …}`), więc
  nie zużywają limitów narzędzi.
- Źródeł węzeł nie liczy sam: czyta `sources` ze stanu, a te powstają z odczytów w `run_tools`.
  Brak źródeł nie jest błędem modelu, więc sam nie wywołuje poprawki. Przy funkcji
  `without_sources` poprawkę wywołuje tylko odpowiedź nie do przyjęcia, jak w każdej sprawie.
- Węzeł nie zna pól wyniku: co zostaje bez źródeł, wie graf, który ten wynik zna. Tak samo jak
  przy `filled_by_graph`.
- Pola od grafu wygrywają z tym, co podał model: tożsamości zgłoszenia model nie ustala.
- W logu przebiegu i na INFO jest sam rodzaj błędu. Komunikat dla modelu cytuje wartości
  argumentów, czyli dane klienta, więc idzie tylko na DEBUG.
"""

import logging
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent_nodes.respond.base import RespondNodeBase
from app.agent_nodes.respond.errors import InvalidAnswerError, RespondError
from app.agent_nodes.run_tools import invalid_arguments_message
from app.agent_tools.base import error_as_json
from app.core_util.validation_text import describe_validation_error
from app.engine_llm import ChatMessage

logger = logging.getLogger(__name__)

# Ile razy w jednej sprawie odpowiedź wraca do modelu do poprawki.
MAX_RETRIES = 1

# Funkcja grafu oddająca pola wyniku, które wypełnia graf ze stanu, a nie model.
FilledByGraph = Callable[[BaseModel], Mapping[str, Any]]

# Funkcja grafu oddająca to, co z przyjętego wyniku zostaje, gdy agent nie odczytał żadnego źródła.
WithoutSources = Callable[[BaseModel], BaseModel]


def text_instead_of_answer_message(
    respond_tool_name: str,  # np. "respond_gate_close"
) -> str:
    """
    Description:
    Komunikat dla modelu, gdy odpowiedział samym tekstem zamiast wywołać narzędzie odpowiedzi.

    Example args:
        respond_tool_name="respond_gate_close"

    Example result:
        "Odpowiedź przyjmujemy wyłącznie jako wywołanie narzędzia `respond_gate_close`, nie jako
         zwykły tekst. Wywołaj je teraz, jako jedyne wywołanie w turze."
    """
    message = (
        f"Odpowiedź przyjmujemy wyłącznie jako wywołanie narzędzia `{respond_tool_name}`, "
        f"nie jako zwykły tekst. Wywołaj je teraz, jako jedyne wywołanie w turze."
    )

    return message


def answer_with_other_calls_message(
    respond_tool_name: str,  # np. "respond_search"
) -> str:
    """
    Description:
    Komunikat dla modelu, gdy w jednej turze wywołał narzędzie odpowiedzi razem z innym
    wywołaniem — innym narzędziem albo drugą odpowiedzią.

    Example args:
        respond_tool_name="respond_search"

    Example result:
        "Narzędzie `respond_search` musi być jedynym wywołaniem w turze, więc żadne wywołanie
         z tej tury nie zostało wykonane. Wywołaj `respond_search` ponownie, samo."
    """
    message = (
        f"Narzędzie `{respond_tool_name}` musi być jedynym wywołaniem w turze, więc żadne "
        f"wywołanie z tej tury nie zostało wykonane. Wywołaj `{respond_tool_name}` ponownie, samo."
    )

    return message


def answer_expected_message(
    respond_tool_name: str,  # np. "respond_suggest_solution"
) -> str:
    """
    Description:
    Komunikat dla modelu, gdy zamiast odpowiedzieć wywołał inne narzędzia, a graf ich już nie
    wykonuje — najczęściej dlatego, że sprawa wyczerpała limit tur.

    Example args:
        respond_tool_name="respond_suggest_solution"

    Example result:
        "To wywołanie nie zostało wykonane: w tej sprawie można już tylko odpowiedzieć. Wywołaj
         narzędzie `respond_suggest_solution` na podstawie tego, co już masz."
    """
    message = (
        f"To wywołanie nie zostało wykonane: w tej sprawie można już tylko odpowiedzieć. "
        f"Wywołaj narzędzie `{respond_tool_name}` na podstawie tego, co już masz."
    )

    return message


class RespondNode(RespondNodeBase):
    """
    Description:
    Węzeł właściwy `respond`: zamienia odpowiedź modelu na wynik grafu albo odsyła ją do
    poprawki.

    Do czego:
    Jedyne miejsce, w którym odpowiedź modelu staje się wynikiem, który trasa oddaje wołającemu.
    Dzięki temu dwie reguły wynikają z kodu, a nie z posłuszeństwa modelu: wynik ma zawsze kształt
    modelu wyniku grafu (na przykład blokada bramki zawsze niesie uzasadnienie i wskazówkę),
    a wariant wymagający źródeł bez źródeł nie oddaje treści napisanej „z głowy" (zasada 9) —
    najwyżej to, co graf uznał za niezależne od źródeł. Węzeł jest ten sam w każdym grafie; graf
    podaje mu nazwę swojego narzędzia odpowiedzi i model wyniku (`respond_node()` w pakiecie
    grafu).

    Flow:
        1. Konstruktor przyjmuje nazwę narzędzia odpowiedzi, model wyniku, informację, czy graf
           wymaga źródeł, funkcję oddającą to, co zostaje bez źródeł, i funkcję oddającą pola,
           które wypełnia graf.
        2. `run()` najpierw sprawdza źródła (`_has_sources()`), potem czyta odpowiedź
           (`_read_answer()`) i zapisuje wynik (`output_update()` z klasy wspólnej z atrapą,
           a bez źródeł `_unsourced_update()`).
        3. Odpowiedź nie do przyjęcia `_read_answer()` zgłasza jako `InvalidAnswerError`,
           a `_send_back()` zamienia ją na poprawkę dla modelu albo — gdy poprawka już była —
           na `RespondError`.
    """

    def __init__(
        self,
        respond_tool_name: str,                           # np. "respond_gate_close"
        output_model:      type[BaseModel],               # np. Verdict
        requires_sources:  bool = False,                  # np. True w `suggest_solution`
        without_sources:   WithoutSources | None = None,  # np. suggest_solution.without_sources
        filled_by_graph:   FilledByGraph | None = None,   # np. parse_ticket.filled_by_graph
    ):
        """
        Description:
        Przyjmuje to, co o odpowiedzi wie graf: czym model odpowiada, w jakim kształcie, czy
        odpowiedź wymaga źródeł, co z niej zostaje, gdy źródeł nie ma, i które pola wyniku graf
        wypełnia sam ze stanu.

        Example args:
            respond_tool_name="respond_suggest_solution"
            output_model=Proposal
            requires_sources=True
            without_sources=suggest_solution.without_sources
            filled_by_graph=None

        Example result:
            RespondNode walidujący argumenty `respond_suggest_solution` do `Proposal`, który bez
            źródeł zapisuje same uwagi (`ProposalNotes`)

        Raises:
            ValueError: pusta nazwa narzędzia odpowiedzi albo funkcja `without_sources` w grafie,
                który źródeł nie wymaga
        """
        if not respond_tool_name:
            raise ValueError("węzeł respond bez nazwy narzędzia odpowiedzi — graf źle złożony")

        # Bez wymogu źródeł funkcja nie miałaby kiedy zadziałać — to pomyłka przy składaniu.
        if without_sources is not None and not requires_sources:
            raise ValueError(
                "węzeł respond z funkcją without_sources w grafie, który źródeł nie wymaga — "
                "graf źle złożony"
            )

        self._respond_tool_name = respond_tool_name
        self._output_model      = output_model
        self._requires_sources  = requires_sources
        self._without_sources   = without_sources
        self._filled_by_graph   = filled_by_graph

    async def run(
        self,
        state: BaseModel,  # np. stan grafu po ostatniej turze modelu
    ) -> dict[str, Any]:
        """
        Description:
        Zapisuje wynik grafu z odpowiedzi modelu albo odsyła odpowiedź do poprawki.

        Example args:
            state=GateCloseState(messages=[tool_call_turn("respond_gate_close", {…})], …)

        Example result:
            {"output": Verdict(verdict="pass", …),
             "log": [LogEntry(node="respond", message="output: Verdict")]}

        Raises:
            RespondError: odpowiedzi nie da się przyjąć, a poprawka w tej sprawie już była
            ValueError: graf źle złożony — brak tury modelu albo pola `sources` w stanie
        """
        unsourced = self._requires_sources and not self._has_sources(state)

        # --- graf wymagający źródeł bez źródeł i bez funkcji od grafu: wyniku nie ma ---
        if unsourced and self._without_sources is None:
            update = {
                "log": [self.log_entry("brak źródeł: graf wymaga źródeł, wyniku nie ma")],
            }

            return update

        turn = self._model_turn(state)

        # --- odpowiedź modelu ---
        try:
            output = self._read_answer(state, turn)
        except InvalidAnswerError as invalid:  # nie do przyjęcia: poprawka albo porażka
            return self._send_back(state, turn, invalid)

        # --- bez źródeł: zostaje to, co graf uznał za niezależne od źródeł ---
        if unsourced:
            return self._unsourced_update(output)

        return self.output_update(output)

    def _unsourced_update(
        self,
        output: BaseModel,  # np. Proposal(text="Prosimy o restart usługi.", internal_notes="…")
    ) -> dict[str, Any]:
        """
        Description:
        Składa zmianę stanu po przyjęciu odpowiedzi w sprawie bez źródeł: w `output` trafia to,
        co z wyniku zostawia funkcja grafu `without_sources`, a w logu — że źródeł nie było
        i jaki typ wyniku został.

        Example args:
            output=Proposal(text="Prosimy o restart usługi.", internal_notes="Szukałem…")

        Example result:
            {"output": ProposalNotes(internal_notes="Szukałem…"),
             "log": [LogEntry(node="respond", message="brak źródeł: output: ProposalNotes")]}
        """
        kept = self._without_sources(output)

        update = {
            "output": kept,
            "log":    [self.log_entry(f"brak źródeł: output: {type(kept).__name__}")],
        }

        return update

    def _has_sources(
        self,
        state: BaseModel,  # np. SuggestSolutionState(sources=[SourceRef(…)], …)
    ) -> bool:
        """
        Description:
        Mówi, czy agent odczytał w tej sprawie choć jedno źródło. Źródła powstają z odczytów
        w węźle `run_tools`, nigdy z deklaracji modelu.

        Example args:
            state=SuggestSolutionState(input_text="…", sources=[])

        Example result:
            False

        Raises:
            ValueError: stan grafu nie ma pola `sources`, a graf wymaga źródeł
        """
        if not hasattr(state, "sources"):
            raise ValueError("graf wymaga źródeł, a jego stan nie ma pola sources — źle złożony")

        return bool(state.sources)

    def _model_turn(
        self,
        state: BaseModel,  # np. stan grafu z messages=[…, ChatMessage(role="assistant", …)]
    ) -> ChatMessage:
        """
        Description:
        Oddaje ostatnią turę modelu, czyli ostatnią wiadomość rozmowy.

        Example args:
            state=GateCloseState(messages=[tool_call_turn("respond_gate_close", {…})], …)

        Example result:
            ChatMessage(role="assistant", tool_calls=[ToolCall(name="respond_gate_close", …)])

        Raises:
            ValueError: rozmowa jest pusta albo nie kończy się turą modelu
        """
        if not state.messages or state.messages[-1].role != "assistant":
            raise ValueError("węzeł respond bez tury modelu — graf źle złożony")

        return state.messages[-1]

    def _read_answer(
        self,
        state: BaseModel,    # np. ParseTicketState(ticket_id="90101", …)
        turn:  ChatMessage,  # ostatnia tura modelu
    ) -> BaseModel:
        """
        Description:
        Zamienia turę modelu na wynik grafu: tura musi być jednym wywołaniem narzędzia
        odpowiedzi, a jego argumenty — razem z polami od grafu — muszą przejść walidację modelu
        wyniku.

        Example args:
            state=GateCloseState(input_text="…", rules=["…"])
            turn=tool_call_turn("respond_gate_close", {"verdict": "pass"})

        Example result:
            Verdict(verdict="pass", reasons=[], missing=[], hint="")

        Raises:
            InvalidAnswerError: sam tekst, brak wywołania odpowiedzi, odpowiedź razem z innym
                wywołaniem albo argumenty odrzucone przez model wyniku
        """
        name  = self._respond_tool_name
        calls = turn.tool_calls

        # --- sam tekst: zwykły przypadek u dostawcy, który nie wymusza wywołania narzędzia ---
        if not calls:
            raise InvalidAnswerError(
                "tekst zamiast narzędzia",
                text_instead_of_answer_message(name),
            )

        # --- same inne narzędzia: sprawa ucięta limitem tur, zanim model odpowiedział ---
        if all(call.name != name for call in calls):
            raise InvalidAnswerError("brak wywołania odpowiedzi", answer_expected_message(name))

        # --- odpowiedź razem z innym wywołaniem ---
        if len(calls) > 1:
            raise InvalidAnswerError(
                "odpowiedź z innym wywołaniem",
                answer_with_other_calls_message(name),
            )

        # --- argumenty: pola od grafu wygrywają z tym, co podał model ---
        filled    = self._filled_by_graph(state) if self._filled_by_graph else {}
        arguments = {**calls[0].arguments, **filled}

        try:
            output = self._output_model.model_validate(arguments)
        except ValidationError as exc:
            problems = describe_validation_error(exc)

            # `from None`: błąd Pydantica cytuje wartości argumentów — nie do logów ze stosem.
            raise InvalidAnswerError(
                "błędne argumenty",
                invalid_arguments_message(name, problems),
            ) from None

        return output

    def _send_back(
        self,
        state:   BaseModel,           # np. GateCloseState(respond_retries=0, …)
        turn:    ChatMessage,         # odrzucona tura modelu
        invalid: InvalidAnswerError,  # co było nie tak; komunikat czyta model
    ) -> dict[str, Any]:
        """
        Description:
        Odsyła odrzuconą odpowiedź do modelu: składa zmianę stanu z komunikatem o błędzie
        i podbitym licznikiem poprawek. Gdy poprawka w tej sprawie już była, kończy przebieg
        błędem.

        Example args:
            state=GateCloseState(input_text="…", rules=["…"], respond_retries=0)
            turn=ChatMessage(role="assistant", content="Zgłoszenie można zamknąć.")
            invalid=InvalidAnswerError("tekst zamiast narzędzia", "Odpowiedź przyjmujemy…")

        Example result:
            {"messages": [ChatMessage(role="user", content="Odpowiedź przyjmujemy wyłącznie…")],
             "respond_retries": 1,
             "log": [LogEntry(node="respond", message="do poprawki: tekst zamiast narzędzia")]}

        Raises:
            RespondError: poprawka w tej sprawie już była
        """
        name = self._respond_tool_name

        # Sam rodzaj błędu na INFO; komunikat cytuje argumenty, czyli dane klienta.
        logger.info("respond tool=%s invalid_answer=%s", name, invalid.reason)
        logger.debug("respond tool=%s invalid_answer_message=%s", name, invalid)

        # --- poprawka już była: porażka, nie pętla ---
        if state.respond_retries >= MAX_RETRIES:
            raise RespondError(
                f"model nie oddał poprawnej odpowiedzi narzędziem `{name}` mimo poprawki: "
                f"{invalid.reason}"
            )

        update = {
            "messages":        self._feedback(turn, str(invalid)),
            "respond_retries": state.respond_retries + 1,
            "log":             [self.log_entry(f"do poprawki: {invalid.reason}")],
        }

        return update

    @staticmethod
    def _feedback(
        turn:    ChatMessage,  # odrzucona tura modelu
        message: str,          # np. "Błędne argumenty narzędzia `respond_gate_close`: …"
    ) -> list[ChatMessage]:
        """
        Description:
        Zamienia komunikat o błędzie na wiadomości, które model dostanie w turze poprawki. Każde
        wywołanie z odrzuconej tury dostaje błąd w miejscu wyniku narzędzia; tura bez wywołań
        dostaje zwykłą wiadomość, bo nie ma w niej wywołania, na które dałoby się odpowiedzieć.

        Example args:
            turn=tool_call_turn("respond_gate_close", {"verdict": "block"}, call_id="call_1")
            message="Błędne argumenty narzędzia `respond_gate_close`: …"

        Example result:
            [ChatMessage(role="tool", call_id="call_1", content='{"error": "Błędne argumenty…"}')]
        """
        # --- sam tekst: nie ma wywołania, na które odpowiada wiadomość `tool` ---
        if not turn.tool_calls:
            return [ChatMessage(role="user", content=message)]

        # --- wywołania: dostawca nie przyjmie rozmowy, w której któreś zostało bez odpowiedzi ---
        feedback = [
            ChatMessage(role="tool", call_id=call.call_id, content=error_as_json(message))
            for call in turn.tool_calls
        ]

        return feedback
