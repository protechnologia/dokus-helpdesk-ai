"""
Description:
Próbki do testu kontraktu grafów (`tests/unit/api_agent_graphs/test_api_agent_graphs_contract.py`):
wynik inny niż domyślny dla atrapy każdego grafu. Dzięki nim plik testu to same testy, a dane,
na których stoją asercje, leżą obok helpera grafów.

| co              | do czego                                                            |
|-----------------|---------------------------------------------------------------------|
| `BLOCK`         | werdykt bramki inny niż domyślny: blokada z brakiem i wskazówką     |
| `GIVEN_OUTPUTS` | wynik podawany atrapie każdego grafu, którego wynik ma treść        |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test importuje je z tego modułu.
- Graf, którego brakuje w `GIVEN_OUTPUTS`, wywraca test atrapy: nowy graf trzeba tu dopisać
  świadomie.
"""

from pydantic import BaseModel

from app.agent_graphs import parse_ticket
from app.agent_graphs.polish import PolishedText
from app.agent_graphs.search import SearchNotes
from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.verdict import Verdict

# Werdykt bramki inny niż domyślny: blokada z uzasadnieniem, brakiem i wskazówką.
BLOCK = Verdict(
    verdict = "block",
    reasons = ["Nie widać, co było przyczyną."],
    missing = ["przyczyna"],
    hint    = "Dopisz, dlaczego usługa stanęła.",
)

# Wynik inny niż domyślny, podawany atrapie każdego grafu, którego wynik ma treść: test sprawdza,
# że atrapa oddaje dokładnie ten, a nie swój domyślny.
GIVEN_OUTPUTS: dict[str, BaseModel] = {
    "gate_close":        BLOCK,
    "gate_reply":        BLOCK,
    "parse_ticket":      parse_ticket.default_ticket().model_copy(update={"cause": "brak"}),
    "polish":            PolishedText(text="Dzień dobry, przesyłki już docierają."),
    "search":            SearchNotes(internal_notes="Zgłoszenia: żadnej nie znaleziono."),
    "suggest_handoff":   Proposal(text="Przekazujemy sprawę do dalszych prac.", internal_notes=""),
    "suggest_questions": Proposal(
        text           = "1. Od kiedy nie przychodzą przesyłki?",
        internal_notes = "1: odcina zacięcie kolejki",
    ),
    "suggest_solution":  Proposal(
        text           = "Kroki do wykonania: 1. Prosimy o restart usługi.",
        internal_notes = "- Odpowiedź stoi na jednym zgłoszeniu.",
    ),
}
