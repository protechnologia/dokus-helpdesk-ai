import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from app.agent_nodes.base import Node
from app.agent_nodes.models import ToolTiming
from app.agent_tools import SourceRef
from app.engine_llm import ChatMessage, ToolCall


def tool_timing(
    call_id:    str,       # np. "call_1"
    started_at: datetime,  # np. datetime(2026, 10, 19, 12, 3, 15, 120000, tzinfo=UTC)
    started:    float,     # np. 1834.27 — `time.perf_counter()` na początku wywołania
) -> ToolTiming:
    """
    Description:
    Zapisuje czas wywołania, które właśnie się skończyło. Początek to zegar ścienny, żeby dało
    się go zestawić z innymi krokami, a czas trwania liczy `perf_counter`, bo zegar ścienny
    potrafi przeskoczyć w trakcie wywołania.

    Example args:
        call_id="call_1"
        started_at=datetime(2026, 10, 19, 12, 3, 15, 120000, tzinfo=UTC)
        started=1834.27

    Example result:
        ToolTiming(call_id="call_1", started_at=datetime(2026, 10, 19, 12, 3, 15, 120000, …),
                   duration_ms=84.2)
    """
    timing = ToolTiming(
        call_id     = call_id,
        started_at  = started_at,
        duration_ms = (time.perf_counter() - started) * 1000,
    )

    return timing


def start_clock() -> tuple[datetime, float]:
    """
    Description:
    Odczyt obu zegarów na początku wywołania narzędzia, do podania potem `tool_timing()`.

    Example args:
        (brak)

    Example result:
        (datetime(2026, 10, 19, 12, 3, 15, 120000, tzinfo=UTC), 1834.27)
    """
    return datetime.now(UTC), time.perf_counter()


class RunToolsNodeBase(Node):
    """
    Description:
    To, co wspólne dla węzła `run_tools` i jego atrapy: nazwa i zapis odpowiedzi narzędzi
    w stanie grafu. Węzeł i atrapa różnią się wyłącznie tym, skąd biorą odpowiedź na wywołanie —
    z narzędzia albo z ustaleń testu — więc test na atrapie widzi te same wiadomości `tool`, ten
    sam wpis w logu i te same pomiary czasu co przebieg z narzędziami.
    """

    name = "run_tools"

    def results_update(
        self,
        calls:      Sequence[ToolCall],    # wywołania z ostatniej tury modelu
        texts:      Sequence[str],         # co model dostaje na każde z nich, w ich kolejności
        timings:    Sequence[ToolTiming],  # czas każdego z nich, w ich kolejności
        sources:    Sequence[SourceRef],   # źródła z odczytów wykonanych w tej turze
        over_limit: int = 0,               # ile wywołań dostało odmowę z powodu limitu
        failed:     int = 0,               # ile wywołań dostało inny błąd zamiast wyniku
    ) -> dict[str, Any]:
        """
        Description:
        Składa zmianę stanu po wykonaniu narzędzi: po jednej wiadomości `tool` i jednym pomiarze
        czasu na wywołanie, z jego `call_id`, źródła z odczytów i wpis w logu. W logu są same
        nazwy narzędzi i liczby — argumenty i wyniki to dane klienta. `sources` trafiają do
        zmiany tylko wtedy, gdy są: stan grafu bez narzędzi wiedzy nie ma tego pola.

        Example args:
            calls=[ToolCall(call_id="call_2", name="read_tickets_card", arguments={…})]
            texts=['{"cards": [{"ticket_id": "90001", …}], "without_card": []}']
            timings=[ToolTiming(call_id="call_2", started_at=…, duration_ms=84.2)]
            sources=[SourceRef(source="tickets", item_id="90001", title="Nie przychodzą…")]
            over_limit=0
            failed=0

        Example result:
            {"messages": [ChatMessage(role="tool", call_id="call_2", content='{"cards": […]}')],
             "log": [LogEntry(node="run_tools",
                              message="wywołania: read_tickets_card; źródła: 1")],
             "tool_timings": [ToolTiming(call_id="call_2", …)],
             "sources": [SourceRef(source="tickets", item_id="90001", …)]}

        Raises:
            ValueError: pomiary nie odpowiadają wywołaniom — węzeł zgubił albo przestawił pomiar
        """
        results = [
            ChatMessage(role="tool", call_id=call.call_id, content=text)
            for call, text in zip(calls, texts, strict=True)
        ]

        # Pomiar wskazuje wywołanie po `call_id`, więc musi go mieć każde, w kolejności tury.
        if [timing.call_id for timing in timings] != [call.call_id for call in calls]:
            raise ValueError("pomiary czasu nie odpowiadają wywołaniom z tury modelu")

        # --- wpis w logu: nazwy i liczby ---
        names   = ", ".join(call.name for call in calls) or "brak"
        summary = f"wywołania: {names}; źródła: {len(sources)}"

        if over_limit:
            summary += f"; ponad limit: {over_limit}"

        if failed:
            summary += f"; błędy: {failed}"

        update: dict[str, Any] = {
            "messages":     results,
            "log":          [self.log_entry(summary)],
            "tool_timings": list(timings),
        }

        if sources:
            update["sources"] = list(sources)

        return update
