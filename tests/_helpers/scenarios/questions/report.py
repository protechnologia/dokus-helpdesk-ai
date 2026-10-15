"""
Description:
Raport scenariuszy „pytań już nie trzeba”: `QuestionsReport` zbiera oceny spraw z jednego
przebiegu pytesta i składa wydruk, który pytest pokazuje po testach — liczniki błędów,
a pod nimi każdą sprawę z oceną i polami wyniku w całości.

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `questions_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
- Pola wyniku wypisuje `field_lines()` z helpera wstrzyknięć, wspólna dla raportów
  scenariuszy, więc zmiana wydruku pól dotyczy wszystkich czterech.
"""

from collections.abc import Sequence

from tests._helpers.scenarios.injections import field_lines
from tests._helpers.scenarios.questions.models.questions_outcome import QuestionsOutcome


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
