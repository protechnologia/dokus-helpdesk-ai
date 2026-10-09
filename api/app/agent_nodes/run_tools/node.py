"""
Description:
Węzeł `run_tools`: wykonuje narzędzia, które model wywołał w ostatniej turze, i dokleja ich
odpowiedzi do rozmowy w stanie grafu. To tutaj powstaje lista źródeł odpowiedzi — z tego, co
narzędzia odczytały, a nie z tego, co model deklaruje.

Przed — ostatnia tura modelu zleca dwa odczyty, drugi z numerem, którego nie ma w bazie:

    messages[-1] = ChatMessage(role="assistant", tool_calls=[
        ToolCall(call_id="call_2", name="read_tickets_card",   arguments={"ticket_ids": ["90001"]}),
        ToolCall(call_id="call_3", name="read_tickets_thread", arguments={"ticket_id": "90019"}),
    ])

Po — zmiana stanu (tu na atrapach narzędzi):

    {
        "messages": [ChatMessage(role="tool", call_id="call_2",
                                 content='{\\n  "cards": [\\n    {\\n      "ticket_id": "90001",…'),
                     ChatMessage(role="tool", call_id="call_3",
                                 content='{"error": "nieznane zgłoszenie: 90019"}')],
        "log":      [LogEntry(node="run_tools",
                              message="wywołania: read_tickets_card, read_tickets_thread; "
                                      "źródła: 1; błędy: 1")],
        "sources":  [SourceRef(source="tickets", item_id="90001",
                               title="Nie przychodzą przesyłki z e-Doręczeń",
                               date=date(2026, 2, 10))],
    }

Co się dzieje po drodze, dla każdego wywołania po kolei:

1. Wywołanie ponad limit swojego narzędzia dostaje odmowę (`limits.py`) i nie jest wykonywane.
2. Nazwa musi wskazywać narzędzie, które węzeł dostał — czyli dozwolone w tym grafie.
3. Argumenty waliduje klasa argumentów narzędzia (`query_model` albo `args_model`).
4. Narzędzie się wykonuje: źródło wiedzy oddaje tekst dla modelu (`render_for_model()`)
   i źródła (`cite()`), a narzędzie pomocnicze — wyszukiwanie, spis, odczyt pliku kodu —
   sam tekst.
5. Gdy krok 2, 3 albo 4 skończy się `ToolCallError`, model dostaje w miejscu wyniku
   `{"error": …}` i może poprawić wywołanie w następnej turze.

O czym pamiętać przy zmianach:

- Każde wywołanie dostaje dokładnie jedną wiadomość `tool` ze swoim `call_id`, także odrzucone:
  dostawca nie przyjmie rozmowy z wywołaniem bez odpowiedzi.
- Do modelu wraca wyłącznie `ToolCallError`. Awarii embeddera, Qdranta albo Postgresa węzeł nie
  łapie: zatrzymuje przebieg, a trasa oddaje 503 — poprawione wywołanie nic by tam nie zmieniło.
- Źródła powstają tylko z wykonanych wywołań źródeł wiedzy. Narzędzie pomocnicze nie ma
  `cite()`, a wywołanie zakończone błędem niczego nie dokłada.
- Narzędzia idą po kolei, w kolejności z tury modelu — tak też są liczone wobec limitów.
- Węzeł wykonuje to, co dostał w konstruktorze. Że są to narzędzia dozwolone w grafie, pilnuje
  składający: tę samą listę podaje `model_tools()` grafu, które odrzuca narzędzie spoza
  `TOOL_NAMES`.
- Wywołania narzędzia odpowiedzi (`respond_<graf>`) węzeł nie widzi: po nim graf idzie do
  `respond` (`route_after_agent`).
"""

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent_nodes.run_tools.base import RunToolsNodeBase
from app.agent_nodes.run_tools.limits import calls_over_limit, limit_exceeded_text
from app.agent_tools import AgentTool, KnowledgeSource, SourceRef, ToolCallError
from app.agent_tools.base import arguments_model_of, error_as_json
from app.core_util.validation_text import describe_validation_error
from app.engine_llm import ToolCall

logger = logging.getLogger(__name__)


def unknown_tool_message(
    tool_name: str,  # np. "find_tickets"
) -> str:
    """
    Description:
    Komunikat dla modelu, gdy wywołał narzędzie, którego w tym grafie nie ma — zmyśloną nazwę
    albo narzędzie niedostępne dla tej funkcji.

    Example args:
        tool_name="find_tickets"

    Example result:
        "Narzędzie `find_tickets` nie istnieje. Użyj jednego z narzędzi, które masz do dyspozycji."
    """
    message = (
        f"Narzędzie `{tool_name}` nie istnieje. "
        f"Użyj jednego z narzędzi, które masz do dyspozycji."
    )

    return message


def invalid_arguments_message(
    tool_name: str,            # np. "find_tickets_vector"
    problems:  Sequence[str],  # np. ["symptoms: Field required"]
) -> str:
    """
    Description:
    Komunikat dla modelu, gdy argumenty wywołania nie przeszły walidacji: które narzędzie i co
    jest nie tak z każdym polem, po jednej pozycji na błąd.

    Example args:
        tool_name="find_tickets_vector"
        problems=["symptoms: Field required", "limit: Extra inputs are not permitted"]

    Example result:
        "Błędne argumenty narzędzia `find_tickets_vector`: symptoms: Field required; limit: Extra
         inputs are not permitted. Popraw argumenty i wywołaj narzędzie ponownie."
    """
    message = (
        f"Błędne argumenty narzędzia `{tool_name}`: {'; '.join(problems)}. "
        f"Popraw argumenty i wywołaj narzędzie ponownie."
    )

    return message


class RunToolsNode(RunToolsNodeBase):
    """
    Description:
    Węzeł właściwy `run_tools`: wykonuje wywołania narzędzi z ostatniej tury modelu i zapisuje
    ich odpowiedzi w stanie grafu.

    Do czego:
    Jedyny węzeł, który woła narzędzia agenta. Dostaje narzędzia dozwolone w grafie i limity
    ich wywołań, więc jest ten sam w każdym grafie z pętlą. To on rozdziela wynik odczytu na
    dwie rzeczy: tekst dla modelu trafia do `messages`, a źródła do `sources` — lista źródeł
    powstaje z wywołań, nigdy z deklaracji modelu (zasada 9).

    Flow:
        1. Konstruktor przyjmuje narzędzia i limity; narzędzie bez limitu albo dwa o jednej
           nazwie to błąd składania.
        2. `run()` wskazuje wywołania ponad limit (`calls_over_limit()`), a pozostałe wykonuje
           po kolei przez `_execute()`.
        3. `_execute()` znajduje narzędzie, waliduje argumenty i woła je; czego nie da się
           wykonać z winy wywołania, zgłasza jako `ToolCallError`.
        4. `results_update()` z klasy wspólnej z atrapą składa zmianę stanu.
    """

    def __init__(
        self,
        tools:  Sequence[AgentTool],  # np. [FindTicketsVectorTool(…), ReadTicketsCardTool(…)]
        limits: Mapping[str, int],    # np. Settings().tool_call_limits()
    ):
        """
        Description:
        Przyjmuje narzędzia, które wolno wykonać w tym grafie, i limity ich wywołań w jednej
        sprawie.

        Example args:
            tools=[FakeFindTicketsVectorTool(), FakeReadTicketsCardTool()]
            limits={"find_tickets_vector": 5, "read_tickets_card": 5}

        Example result:
            RunToolsNode wykonujący te dwa narzędzia, każde najwyżej pięć razy w sprawie

        Raises:
            ValueError: brak narzędzi, dwa narzędzia o tej samej nazwie albo narzędzie bez limitu
        """
        # --- graf z pętlą bez narzędzi nie ma czego wykonywać ---
        if not tools:
            raise ValueError("węzeł run_tools bez narzędzi — graf źle złożony")

        names = [tool.name for tool in tools]

        # --- dwa narzędzia pod jedną nazwą: model nie mógłby wskazać, o które mu chodzi ---
        duplicates = sorted({name for name in names if names.count(name) > 1})

        if duplicates:
            raise ValueError(f"narzędzia o tej samej nazwie: {duplicates}")

        # --- narzędzie bez limitu: opis dla modelu obiecuje limit, więc musi tu być ---
        unlimited = [name for name in names if name not in limits]

        if unlimited:
            raise ValueError(f"narzędzia bez limitu wywołań (AGENT_MAX_CALLS_*): {unlimited}")

        self._tools  = {tool.name: tool for tool in tools}
        self._limits = {name: limits[name] for name in names}

    async def run(
        self,
        state: BaseModel,  # np. stan grafu, którego ostatnia wiadomość zleca narzędzia
    ) -> dict[str, Any]:
        """
        Description:
        Wykonuje wywołania narzędzi z ostatniej tury modelu i odpowiada na każde jedną
        wiadomością `tool`.

        Example args:
            state=SearchState(messages=[…, tool_call_turn("read_tickets_card", {…})], …)

        Example result:
            {"messages": [ChatMessage(role="tool", call_id="call_1", content='{"cards": […]}')],
             "log": [LogEntry(node="run_tools",
                              message="wywołania: read_tickets_card; źródła: 3")],
             "sources": [SourceRef(source="tickets", item_id="90001", …), …]}

        Raises:
            EmbeddingError: embedder jest nieosiągalny albo odpowiedział błędem
            DbQdrantError: Qdrant jest nieosiągalny albo odpowiedział błędem
            DbPostgresError: Postgres jest nieosiągalny albo odpowiedział błędem
        """
        calls      = state.messages[-1].tool_calls if state.messages else []
        over_limit = calls_over_limit(state.messages, self._limits)

        texts:   list[str]       = []
        sources: list[SourceRef] = []
        failed:  int             = 0

        for call in calls:
            # --- ponad limit: odmowa zamiast wykonania ---
            if call.call_id in over_limit:
                texts.append(limit_exceeded_text(call.name, self._limits[call.name]))
                continue

            # --- wykonanie ---
            try:
                text, refs = await self._execute(call)
            except ToolCallError as exc:  # wywołania nie da się wykonać: błąd wraca do modelu
                failed += 1
                texts.append(error_as_json(str(exc)))

                # Sama nazwa na INFO; komunikat może cytować argumenty, czyli dane klienta.
                logger.info("run_tools tool=%s call_error", call.name)
                logger.debug("run_tools tool=%s call_error=%s", call.name, exc)
                continue

            texts.append(text)
            sources.extend(refs)

        update = self.results_update(
            calls      = calls,
            texts      = texts,
            sources    = sources,
            over_limit = len(over_limit),
            failed     = failed,
        )

        return update

    async def _execute(
        self,
        call: ToolCall,  # np. ToolCall(call_id="call_1", name="read_tickets_card", arguments={…})
    ) -> tuple[str, list[SourceRef]]:
        """
        Description:
        Wykonuje jedno wywołanie: znajduje narzędzie, waliduje argumenty jego klasą argumentów
        i woła je. Oddaje tekst dla modelu oraz źródła — niepuste tylko przy odczycie.

        Example args:
            call=ToolCall(call_id="call_1", name="read_tickets_card",
                          arguments={"ticket_ids": ["90001"]})

        Example result:
            ('{"cards": [{"ticket_id": "90001", …}], "without_card": []}',
             [SourceRef(source="tickets", item_id="90001", title="Nie przychodzą…")])

        Raises:
            ToolCallError: nieznane narzędzie, błędne argumenty albo odmowa samego narzędzia
                (np. `UnknownTicketError`)
        """
        # --- narzędzie: tylko z tych, które węzeł dostał ---
        tool = self._tools.get(call.name)

        if tool is None:
            raise ToolCallError(unknown_tool_message(call.name))

        # --- argumenty ---
        try:
            arguments = arguments_model_of(tool).model_validate(call.arguments)
        except ValidationError as exc:
            problems = describe_validation_error(exc)

            # `from None`: błąd Pydantica cytuje wartości argumentów — nie do logów ze stosem.
            raise ToolCallError(invalid_arguments_message(call.name, problems)) from None

        # --- odczyt: tekst dla modelu i źródła z tego samego wyniku ---
        if isinstance(tool, KnowledgeSource):
            result = await tool.search(arguments)

            return tool.render_for_model(result), tool.cite(result)

        # --- wyszukiwanie albo spis: sam tekst, bez źródeł ---
        return await tool.run(arguments), []
