"""
Description:
Zestaw scenariuszy „pytań już nie trzeba” (`data/safe/golden/questions.json`) i ocena sprawy
przeprowadzonej na żywym modelu: czy wariant `suggest_questions` oddał pytania wtedy, gdy fakty
ze zgłoszenia zostawiają konkurujące przyczyny, i brak pytań (`text: null`) wtedy, gdy fakty
rozstrzygają sprawę. Korzysta z niego test ewaluacyjny pytań (p. 59), a raport stąd pytest
wypisuje po przebiegu.

| co                     | do czego                                                        |
|------------------------|-----------------------------------------------------------------|
| `questions_sections()` | sekcje zestawu po nazwie grafu                                  |
| `QuestionsSection`     | sekcja jednego grafu: sprawy                                    |
| `QuestionsCase`        | jedna sprawa: zgłoszenie i to, czy pytania są potrzebne         |
| `judge_questions_case()` | ocena jednej sprawy                                           |
| `QuestionsOutcome`     | wynik oceny: zgodny, pytania zbędne, brak pytań albo brak wyniku |
| `QuestionsReport`      | raport: `record()` dopisuje sprawę, `lines()` składa wydruk     |

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
- Raport dostaje się przez fixture `questions_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
"""

import dataclasses
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from tests.helpers_injections import field_lines

QUESTIONS_FILE = Path("data/safe/golden/questions.json")

# Klucz zestawu z metryczką, a nie sekcja grafu.
META_KEY = "meta"


@dataclasses.dataclass(frozen=True)
class QuestionsCase:
    """Jedna sprawa z zestawu: zgłoszenie i to, czy po jego faktach pytania są potrzebne."""

    case_id:    str   # np. "w01"
    phenomenon: str   # np. "odpowiedzi klienta w wątku rozstrzygają"
    text:       str   # zgłoszenie w kształcie `RawTicket.as_thread()`
    questions:  bool  # np. False — fakty rozstrzygają, oczekiwane `text: null`

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa sprawy w raporcie: identyfikator i zjawisko.

        Example args:
            (brak)

        Example result:
            "w01 odpowiedzi klienta w wątku rozstrzygają"
        """
        return f"{self.case_id} {self.phenomenon}"


@dataclasses.dataclass(frozen=True)
class QuestionsSection:
    """Sekcja zestawu dla jednego grafu: sprawy w kolejności zestawu."""

    graph: str                        # np. "suggest_questions"
    cases: tuple[QuestionsCase, ...]  # sprawy w kolejności zestawu


@dataclasses.dataclass(frozen=True)
class QuestionsOutcome:
    """Ocena jednej sprawy."""

    case:    QuestionsCase      # sprawa, której dotyczy ocena
    asked:   bool | None        # model oddał pytania; None — odpowiedź nie do przyjęcia
    retries: int                # poprawki odpowiedzi od węzła `respond`
    fields:  Mapping[str, Any]  # pola wyniku do raportu; puste, gdy wyniku nie ma

    @property
    def rejected(self) -> bool:
        """
        Description:
        Czy węzeł `respond` nie przyjął odpowiedzi mimo poprawki.

        Example args:
            (brak)

        Example result:
            False
        """
        return self.asked is None

    @property
    def needless(self) -> bool:
        """
        Description:
        Czy model pytał, choć fakty ze zgłoszenia rozstrzygały sprawę.

        Example args:
            (brak)

        Example result:
            True
        """
        return self.asked is True and not self.case.questions

    @property
    def missing(self) -> bool:
        """
        Description:
        Czy model oddał „pytań już nie trzeba”, choć fakty zostawiały konkurujące przyczyny.

        Example args:
            (brak)

        Example result:
            False
        """
        return self.asked is False and self.case.questions

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym zdaniem dla raportu.

        Example args:
            (brak)

        Example result:
            "PYTANIA, CHOĆ SPRAWA ROZSTRZYGNIĘTA"
        """
        # --- odpowiedź nie do przyjęcia: wyniku nie ma ---
        if self.rejected:
            return "ODPOWIEDŹ NIE DO PRZYJĘCIA"

        # --- pytania przy sprawie, którą fakty rozstrzygają ---
        if self.needless:
            return "PYTANIA, CHOĆ SPRAWA ROZSTRZYGNIĘTA"

        # --- brak pytań przy sprawie, której fakty nie rozstrzygają ---
        if self.missing:
            return "BEZ PYTAŃ, CHOĆ PRZYCZYNY KONKURUJĄ"

        return "zgodny"


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


class QuestionsReport:
    """
    Description:
    Zbiera oceny spraw ze scenariuszy pytań w jednym przebiegu pytesta i składa z nich wydruk:
    dla grafu linię z licznikami, a pod nią każdą sprawę z oceną i polami wyniku w całości.

    Do czego:
    Test zalicza zestaw po tym, czy pytania są, ale czy uwagi mówią, które fakty co wykluczyły,
    i czy pytania nie powtarzają tych, na które klient już odpowiedział, widać dopiero w treści.
    Wydruk jest po to, żeby ją przeczytać.

    Flow:
        1. Test dostaje raport przez fixture `questions_report` i woła `record()` raz na sprawę.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            QuestionsReport bez zgłoszonych spraw
        """
        self._records: list[tuple[str, QuestionsOutcome]] = []

    def record(
        self,
        graph:   str,               # np. "suggest_questions"
        outcome: QuestionsOutcome,  # np. judge_questions_case(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednej sprawy.

        Example args:
            graph="suggest_questions"
            outcome=QuestionsOutcome(case=QuestionsCase(case_id="w01", …), asked=False, …)

        Example result:
            None — sprawa jest w raporcie
        """
        self._records.append((graph, outcome))

    def lines(self) -> list[str]:
        """
        Description:
        Składa wydruk: grafy w kolejności zgłoszenia, dla każdego linię z licznikami, a pod nią
        sprawy z oceną, liczbą poprawek i polami wyniku. Pusty raport daje pustą listę.

        Example args:
            (brak)

        Example result:
            ["suggest_questions: pytania zbędne w 0 z 2, brak pytań w 0 z 2, nie do przyjęcia 0",
             "    w01 odpowiedzi klienta w wątku rozstrzygają: zgodny; poprawek 0",
             "        internal_notes: Pytań już nie trzeba: …",
             …]
        """
        graphs = list(dict.fromkeys(graph for graph, _ in self._records))
        lines: list[str] = []

        for graph in graphs:
            outcomes = [outcome for name, outcome in self._records if name == graph]

            lines.append(f"{graph}: {_counts(outcomes)}")

            for outcome in outcomes:
                lines.append(
                    f"    {outcome.case.label}: {outcome.assessment}; poprawek {outcome.retries}"
                )
                lines.extend(field_lines(outcome.fields))

        return lines


def _counts(
    outcomes: Sequence[QuestionsOutcome],  # np. oceny spraw jednego grafu
) -> str:
    """
    Description:
    Liczniki do raportu: pytania zbędne wśród spraw rozstrzygniętych, brak pytań wśród spraw,
    w których przyczyny konkurują, i odpowiedzi nie do przyjęcia.

    Example args:
        outcomes=[QuestionsOutcome(case=QuestionsCase(questions=False, …), asked=True, …), …]

    Example result:
        "pytania zbędne w 1 z 2, brak pytań w 0 z 2, nie do przyjęcia 0"
    """
    settled   = [outcome for outcome in outcomes if not outcome.case.questions]
    contested = [outcome for outcome in outcomes if outcome.case.questions]

    counts = (
        f"pytania zbędne w {sum(outcome.needless for outcome in settled)} z {len(settled)}, "
        f"brak pytań w {sum(outcome.missing for outcome in contested)} z {len(contested)}, "
        f"nie do przyjęcia {sum(outcome.rejected for outcome in outcomes)}"
    )

    return counts
