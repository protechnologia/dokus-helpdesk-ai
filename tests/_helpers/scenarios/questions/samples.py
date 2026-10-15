"""
Description:
Próbki do testów samego helpera „pytań już nie trzeba” (`tests/unit/test_questions_report.py`):
wynik z pytaniami, wynik z samymi uwagami i sprawa o podanym oczekiwaniu. Dzięki nim plik testu
to same testy, a dane, na których stoją asercje, leżą obok helpera, którego dotyczą.

| co                 | do czego                                                 |
|--------------------|----------------------------------------------------------|
| `QUESTIONS`        | wynik z pytaniami do klienta i notatką przy pytaniu      |
| `NO_QUESTIONS`     | wynik bez pytań: same uwagi, że pytań już nie trzeba     |
| `questions_case()` | sprawa, która wymaga pytań albo nie                      |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test helpera importuje je z tego modułu, żeby test
  na żywym modelu nie wziął przez pomyłkę danych testu jednostkowego.
- Dane są zmyślone i nie mają nic wspólnego z zestawem `questions.json`: zestaw zmienia się
  z pomiarami, a próbki tylko razem z oceną.
"""

from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.proposal_notes import ProposalNotes
from tests._helpers.scenarios.questions.models.questions_case import QuestionsCase

# Wynik z pytaniami: treść dla klienta i notatka przy pytaniu w uwagach.
QUESTIONS = Proposal(text="1. Czy była aktualizacja?", internal_notes="1: odcina plik blokady")

# Wynik bez pytań: węzeł odpowiedzi zapisuje wtedy same uwagi dla wdrożeniowca.
NO_QUESTIONS = ProposalNotes(internal_notes="Pytań już nie trzeba: wpis z logu wskazuje 90002.")


def questions_case(
    questions: bool,       # np. False — fakty rozstrzygają sprawę
    case_id:   str = "w",  # np. "w01"
) -> QuestionsCase:
    """
    Description:
    Buduje sprawę z zestawu pytań o podanym oczekiwaniu.

    Example args:
        questions=False
        case_id="w01"

    Example result:
        QuestionsCase(case_id="w01", phenomenon="rozstrzyga", text="ZGŁOSZENIE…", questions=False)
    """
    case = QuestionsCase(
        case_id    = case_id,
        phenomenon = "zawęża" if questions else "rozstrzyga",
        text       = "ZGŁOSZENIE 90701 z 2026-10-08",
        questions  = questions,
    )

    return case
