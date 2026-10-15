"""
Description:
Zestaw scenariuszy „pytań już nie trzeba” (`data/safe/golden/questions.json`) i ocena sprawy
przeprowadzonej na żywym modelu: czy wariant `suggest_questions` oddał pytania wtedy, gdy fakty
ze zgłoszenia zostawiają konkurujące przyczyny, i brak pytań (`text: null`) wtedy, gdy fakty
rozstrzygają sprawę. Korzysta z niego test ewaluacyjny pytań (p. 59). Modele zestawu i oceny
leżą w `models/`, a raport, który pytest wypisuje po przebiegu, w `report.py`.

| co                       | do czego                       |
|--------------------------|--------------------------------|
| `questions_sections()`   | sekcje zestawu po nazwie grafu |
| `judge_questions_case()` | ocena jednej sprawy            |

Przykład — odpowiedzi klienta rozstrzygają sprawę, a model mimo to pyta:

    outcome = judge_questions_case(
        case    = QuestionsCase(case_id="w01", phenomenon="…", text="ZGŁOSZENIE 90701…",
                                questions=False),
        output  = Proposal(text="1. Czy była aktualizacja?", internal_notes="1: …"),
        retries = 0,
    )

    outcome.asked      -> True
    outcome.assessment -> "PYTANIA, CHOĆ SPRAWA ROZSTRZYGNIĘTA"

O czym pamiętać przy zmianach:

- O pytaniach mówi samo pole `text` wyniku: `Proposal` z treścią to pytania, `ProposalNotes`
  (same uwagi) to „pytań już nie trzeba”. Treść pytań i uwag czyta się w raporcie.
- Odpowiedź nie do przyjęcia nie jest ani jednym, ani drugim błędem: helpdesk dostaje wtedy
  503. Liczy się osobno.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from tests._helpers.scenarios.questions.constants import META_KEY, QUESTIONS_FILE
from tests._helpers.scenarios.questions.models.questions_case import QuestionsCase
from tests._helpers.scenarios.questions.models.questions_outcome import QuestionsOutcome
from tests._helpers.scenarios.questions.models.questions_section import QuestionsSection


def questions_sections(
    path: Path = QUESTIONS_FILE,  # np. Path("data/safe/golden/questions.json")
) -> dict[str, QuestionsSection]:
    """
    Description:
    Czyta zestaw scenariuszy pytań i oddaje jego sekcje po nazwie grafu, bez metryczki.

    Example args:
        path=Path("data/safe/golden/questions.json")

    Example result:
        {"suggest_questions": QuestionsSection(graph="suggest_questions",
                                               cases=(QuestionsCase(case_id="w01", …), …))}
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    sections = {
        graph: QuestionsSection(
            graph = graph,
            cases = tuple(_case_from(entry) for entry in body["cases"]),
        )
        for graph, body in raw.items()
        if graph != META_KEY
    }

    return sections


def _case_from(
    entry: Mapping[str, Any],  # np. {"id": "w01", "phenomenon": "…", "questions": false, …}
) -> QuestionsCase:
    """
    Description:
    Zamienia wpis sprawy z zestawu na `QuestionsCase`; nazwy pól zestawu są krótsze.

    Example args:
        entry={"id": "w01", "phenomenon": "…", "questions": False, "input": "ZGŁOSZENIE…"}

    Example result:
        QuestionsCase(case_id="w01", phenomenon="…", text="ZGŁOSZENIE…", questions=False)
    """
    case = QuestionsCase(
        case_id    = entry["id"],
        phenomenon = entry["phenomenon"],
        text       = entry["input"],
        questions  = entry["questions"],
    )

    return case


def judge_questions_case(
    case:    QuestionsCase,     # np. QuestionsCase(case_id="w01", questions=False, …)
    output:  BaseModel | None,  # np. ProposalNotes(…); None — `respond` nie przyjął odpowiedzi
    retries: int,               # np. 0 — poprawki odpowiedzi od węzła `respond`
) -> QuestionsOutcome:
    """
    Description:
    Ocenia jedną sprawę: pytania są, gdy wynik ma niepuste pole `text`; brak wyniku zapisuje
    jako odpowiedź nie do przyjęcia.

    Example args:
        case=QuestionsCase(case_id="w01", questions=False, …)
        output=ProposalNotes(internal_notes="Pytań już nie trzeba: …")
        retries=0

    Example result:
        QuestionsOutcome(case=QuestionsCase(case_id="w01", …), asked=False, retries=0,
                         fields={"internal_notes": "Pytań już nie trzeba: …"})
    """
    # --- brak wyniku: węzeł `respond` nie przyjął odpowiedzi mimo poprawki ---
    if output is None:
        rejected = QuestionsOutcome(
            case    = case,
            asked   = None,
            retries = retries,
            fields  = {},
        )

        return rejected

    fields = output.model_dump(mode="json")

    outcome = QuestionsOutcome(
        case    = case,
        asked   = bool(fields.get("text")),
        retries = retries,
        fields  = fields,
    )

    return outcome
