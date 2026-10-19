"""
Description:
Grafy funkcji produktu: każdy to anonimizacja → pętla agenta z narzędziami → odpowiedź.
Importuj wspólne elementy stąd (`from app.agent_graphs import GraphState`).

Do czego:
Tutaj (`base.py`) to, czego potrzebują stany wszystkich grafów: pola wspólne (`GraphState`)
i reduktor `merge_sources` dla grafów ze źródłami, oraz uruchomienie grafu: w całości
(`run_graph`) albo krok po kroku (`stream_graph`, kroki to `GraphStep` z `models.py`). W katalogu
każdego grafu: przebieg
(`graph.py`), stan dziedziczący po `GraphState` (`state.py`), atrapa grafu (`fake.py`), prompty
i opis narzędzia odpowiedzi (`.md`). Opisy narzędzi agenta leżą przy narzędziach, w `agent_tools/`.

Import tego pakietu wyłącza LangSmith (niżej), więc żaden graf nie ruszy z włączonym tracingiem.

Atrapy wspólne dla grafów z narzędziami wiedzy leżą w `fake.py` tego pakietu.

Fabryka, z której trasy biorą grafy, leży w `factory.py`. Nie jest stąd eksportowana: czyta
konfigurację i pociąga klientów modelu, anonimizatora i baz — a ten plik importuje każdy graf.
Przy atrapie modelu oddaje atrapę grafu, przy prawdziwym dostawcy graf z węzłów właściwych.

Grafy. Bez narzędzi wiedzy przebieg to anonymize → agent → respond, z nimi anonymize → agent ⇄
run_tools → respond, gdzie pętlę ucina limit tur modelu (`AGENT_MAX_ITERATIONS`). Każdy kończy
się wywołaniem `respond_<graf>`; odpowiedź, której nie da się przyjąć, `respond` odsyła modelowi
do poprawki, raz (respond → agent):

| graf                | narzędzia                      | wynik          |
|---------------------|--------------------------------|----------------|
| `gate_close`        | —                              | `Verdict`      |
| `gate_reply`        | —                              | `Verdict`      |
| `search`            | zgłoszenia, dokumentacja i kod | `SearchNotes`  |
| `parse_ticket`      | —                              | `ParsedTicket` |
| `suggest_questions` | zgłoszenia, dokumentacja i kod | `Proposal`     |
| `suggest_solution`  | zgłoszenia, dokumentacja i kod | `Proposal`     |
| `suggest_handoff`   | —                              | `Proposal`     |
| `polish`            | —                              | `PolishedText` |

„Zgłoszenia, dokumentacja i kod" to wszystkie narzędzia z `agent_tools/`: dwa wyszukiwania i dwa
odczyty zgłoszeń, spis treści, dwa wyszukiwania i odczyt dokumentacji oraz cztery narzędzia kodu
aplikacji: szukanie, spis katalogu, odczyt pliku i cytowanie fragmentu.
"""

import langsmith

from app.agent_graphs.base import (
    GraphState,
    graph_step,
    merge_sources,
    route_after_agent,
    route_after_respond,
    run_graph,
    stream_graph,
    tool_definitions,
)
from app.agent_graphs.models import GraphStep, ToolCallRun

# LangSmith zablokowany jawnie: przy LANGSMITH_TRACING=true LangGraph wysyła do chmury stan
# każdego węzła, także `input_text` sprzed anonimizacji. Przełącznik globalny wygrywa z ENV.
langsmith.configure(enabled=False)

__all__ = [
    "GraphState",
    "GraphStep",
    "ToolCallRun",
    "graph_step",
    "merge_sources",
    "route_after_agent",
    "route_after_respond",
    "run_graph",
    "stream_graph",
    "tool_definitions",
]
