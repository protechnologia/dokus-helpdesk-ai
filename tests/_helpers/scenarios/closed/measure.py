"""
Description:
Przebieg scenariuszy trasy zamknięcia zgłoszenia na żywym, płatnym modelu: `measure_closed_cases()`
wysyła każdą sprawę zestawu do trasy `POST /tickets/closed`, ocenia odpowiedź i zgłasza ją do
raportu zużycia i raportu ocen.

Trasa chodzi naprawdę: bramka zamknięcia i karta są grafami z węzłów właściwych na modelu
generującym z `.env`, złożonymi tą samą funkcją co w fabryce grafów (`build_real_graph()`), a za
nimi stoją filtr jakości i serwis korpusu. Atrapami są anonimizator (tekst bez zmian, jak
w pozostałych testach na żywym modelu) oraz embedder, kolekcja zgłoszeń i tabela wątków; pliki
korpusu trafiają do katalogu testu.

O czym pamiętać przy zmianach:

- Woła płatny model: używa go wyłącznie test `llm_live`, przez fixture `outcomes`.
- Klient modelu powstaje na każde żądanie, razem z grafem, jak w fabryce grafów.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs.factory import build_real_graph, get_graph_builder
from app.agent_nodes.models import LogEntry
from app.config import LLMSettings, Settings
from app.core_service.factory_closed_ticket_indexer import get_closed_ticket_indexer
from app.engine_anonymization import FakeAnonymizer
from app.engine_llm import LLMUsage, get_llm_client
from app.main import create_app
from tests._helpers.live import LiveUsageReport
from tests._helpers.scenarios.closed.helper import closed_cases, judge_closed_case
from tests._helpers.scenarios.closed.models.closed_outcome import ClosedOutcome
from tests._helpers.scenarios.closed.report import ClosedReport
from tests._helpers.tickets_index import FakeThreads, FakeTickets, closed_ticket_indexer_on


def measure_closed_cases(
    llm:           LLMSettings,      # np. live_generation_llm(request.config)
    root:          Path,             # np. tmp_path_factory.mktemp("korpus") — korpus testu
    live_usage:    LiveUsageReport,  # raport zużycia przebiegu
    closed_report: ClosedReport,     # raport ocen spraw
) -> list[ClosedOutcome]:
    """
    Description:
    Wysyła wszystkie sprawy zestawu do trasy zamknięcia na żywym modelu, ocenia odpowiedzi,
    zgłasza je do obu raportów i oddaje oceny. Sprawa, na którą trasa nie oddała wyniku, też
    jest oceniona — jako błąd trasy.

    Example args:
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        root=Path("/tmp/pytest-0/korpus0")
        live_usage=LiveUsageReport()
        closed_report=ClosedReport()

    Example result:
        [ClosedOutcome(case=ClosedCase(case_id="c01", …), status=200, answer="indexed", …), …]
    """
    judged: list[ClosedOutcome] = []

    with TestClient(_live_app(llm, root), raise_server_exceptions=False) as client:
        for case in closed_cases():
            response = client.post("/tickets/closed", json=dict(case.request))
            body     = response.json()

            # --- sprawa z wynikiem: zużycie obu grafów do raportu ---
            if response.status_code == 200:
                live_usage.record(f"trasa /tickets/closed: {case.label}", *_usage_and_log(body))

            outcome = judge_closed_case(case, response.status_code, body)

            closed_report.record(outcome)
            judged.append(outcome)

    return judged


def _live_app(
    llm:  LLMSettings,  # np. live_generation_llm(request.config)
    root: Path,         # np. Path("/tmp/pytest-0/korpus0")
) -> FastAPI:
    """
    Description:
    Aplikacja, w której trasa zamknięcia dostaje grafy na żywym modelu i atrapie anonimizatora
    oraz serwis korpusu na katalogu testu i atrapach baz.

    Example args:
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", …)
        root=Path("/tmp/pytest-0/korpus0")

    Example result:
        FastAPI, której `POST /tickets/closed` woła prawdziwy model
    """
    settings = Settings()
    corpus   = closed_ticket_indexer_on(root, FakeTickets(), FakeThreads())

    def build(
        module,  # np. app.agent_graphs.gate_close
    ) -> CompiledStateGraph:
        """
        Description:
        Składa graf tak jak fabryka przy prawdziwym dostawcy, z atrapą anonimizatora i bez
        narzędzi: bramka i karta ich nie mają.

        Example args:
            module=app.agent_graphs.gate_close

        Example result:
            CompiledStateGraph z węzłów właściwych na modelu z `.env`
        """
        graph = build_real_graph(
            graph          = module,
            llm            = get_llm_client(llm),
            anonymizer     = FakeAnonymizer(),
            tools          = (),
            limits         = settings.tool_call_limits(),
            max_iterations = settings.agent_max_iterations,
        )

        return graph

    app = create_app()
    app.dependency_overrides[get_graph_builder]         = lambda: build
    app.dependency_overrides[get_closed_ticket_indexer] = lambda: corpus

    return app


def _usage_and_log(
    body: dict,  # odpowiedź trasy, np. {"usage": {"llm_calls": 2, …}, "log": [{…}, …], …}
) -> tuple[LLMUsage, list[LogEntry]]:
    """
    Description:
    Zużycie i log obu grafów z odpowiedzi trasy, w kształcie, który przyjmuje raport zużycia.
    Rozmowy z modelem trasa nie oddaje, więc raport pokaże przebieg bez wywołań narzędzi.

    Example args:
        body={"usage": {"llm_calls": 2, "prompt_tokens": 3100, …}, "log": [{"node": "agent", …}]}

    Example result:
        (LLMUsage(calls=2, prompt_tokens=3100, …), [LogEntry(node="agent", message="tura 1: …")])
    """
    usage = body["usage"]

    total = LLMUsage(
        calls              = usage["llm_calls"],
        prompt_tokens      = usage["prompt_tokens"],
        completion_tokens  = usage["completion_tokens"],
        cache_write_tokens = usage["cache_write_tokens"],
        cache_read_tokens  = usage["cache_read_tokens"],
        cost_usd           = usage["cost_usd"],
    )
    log = [LogEntry(node=entry["node"], message=entry["message"]) for entry in body["log"]]

    return total, log
