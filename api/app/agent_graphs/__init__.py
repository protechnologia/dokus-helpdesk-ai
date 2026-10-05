"""
Description:
Grafy funkcji produktu: każdy to anonimizacja → pętla agenta z narzędziami → odpowiedź.
Importuj wspólne elementy stąd (`from app.agent_graphs import GraphState`).

Do czego:
Tutaj (`base.py`) to, czego potrzebują stany wszystkich grafów: pola wspólne (`GraphState`)
i reduktor `merge_sources` dla grafów ze źródłami. W katalogu każdego grafu: przebieg
(`graph.py`), stan dziedziczący po `GraphState` (`state.py`), atrapa grafu (`fake.py`), prompty
i opis narzędzia odpowiedzi (`.md`). Opisy narzędzi agenta leżą przy narzędziach, w `agent_tools/`.

Import tego pakietu wyłącza LangSmith (niżej), więc żaden graf nie ruszy z włączonym tracingiem.

Atrapy wspólne dla grafów z narzędziami wiedzy leżą w `fake.py` tego pakietu.

Fabryka, z której trasy biorą grafy, leży w `factory.py`. Nie jest stąd eksportowana: czyta
konfigurację, a po p. 11 pociągnie też klientów — a ten plik importuje każdy graf.

Grafy (CLAUDE.md -> „Plan", p. 5; trasy biorą je dziś złożone z atrap węzłów). Bez narzędzi
wiedzy przebieg to anonymize → agent → respond, z nimi anonymize → agent ⇄ run_tools → respond,
gdzie pętlę ucina limit tur modelu (`AGENT_MAX_ITERATIONS`). Każdy kończy się wywołaniem
`respond_<graf>`:

| graf                | narzędzia                 | wynik          |
|---------------------|---------------------------|----------------|
| `gate_close`        | —                         | `Verdict`      |
| `gate_reply`        | —                         | `Verdict`      |
| `search`            | zgłoszenia i dokumentacja | `SearchDone`   |
| `parse_ticket`      | —                         | `ParsedTicket` |
| `suggest_questions` | zgłoszenia i dokumentacja | `Proposal`     |
| `suggest_solution`  | zgłoszenia i dokumentacja | `Proposal`     |
| `suggest_handoff`   | —                         | `Proposal`     |
| `polish`            | —                         | `PolishedText` |

„Zgłoszenia i dokumentacja" to wszystkie osiem narzędzi z `agent_tools/`: dwa wyszukiwania i dwa
odczyty zgłoszeń oraz spis treści, dwa wyszukiwania i odczyt dokumentacji.
"""

import langsmith

from app.agent_graphs.base import (
    GraphState,
    merge_sources,
    route_after_agent,
    run_graph,
    tool_definitions,
)

# LangSmith zablokowany jawnie: przy LANGSMITH_TRACING=true LangGraph wysyła do chmury stan
# każdego węzła, także `input_text` sprzed anonimizacji. Przełącznik globalny wygrywa z ENV.
langsmith.configure(enabled=False)

__all__ = [
    "GraphState",
    "merge_sources",
    "route_after_agent",
    "run_graph",
    "tool_definitions",
]
