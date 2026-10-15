"""
Description:
Raport scenariuszy rozwiązania: `SolutionReport` zbiera oceny spraw z jednego przebiegu pytesta
i składa wydruk, który pytest pokazuje po testach — liczniki błędów, a pod nimi każdą sprawę
z oceną, licznikami (źródła, wzmianka oczekiwana i niepożądana) i polami wyniku w całości.

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `solution_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
- Pola wyniku wypisuje `field_lines()` z helpera wstrzyknięć, wspólna dla raportów
  scenariuszy, więc zmiana wydruku pól dotyczy wszystkich.
"""

from collections.abc import Sequence

from tests._helpers.scenarios.injections import field_lines
from tests._helpers.scenarios.solution.models.solution_outcome import SolutionOutcome


class SolutionReport:
    """
    Description:
    Zbiera oceny spraw ze scenariuszy rozwiązania w jednym przebiegu pytesta i składa z nich
    wydruk: dla grafu linię z licznikami, a pod nią każdą sprawę z oceną, licznikami i polami
    wyniku w całości.

    Do czego:
    Test zalicza zestaw po faktach z karty w treści dla klienta, ale czy propozycja nie powtarza
    kroku, który klient już wykonał, i czy nie dopisuje nieodwracalności, której w materiale nie
    ma, mówią liczniki, a jak model to napisał — dopiero treść. Wydruk jest po to, żeby ją
    przeczytać.

    Flow:
        1. Test dostaje raport przez fixture `solution_report` i woła `record()` raz na sprawę.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            SolutionReport bez zgłoszonych spraw
        """
        self._records: list[tuple[str, SolutionOutcome]] = []

    def record(
        self,
        graph:   str,              # np. "suggest_solution"
        outcome: SolutionOutcome,  # np. judge_solution_case(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednej sprawy.

        Example args:
            graph="suggest_solution"
            outcome=SolutionOutcome(case=SolutionCase(case_id="r03", …), missing=(), …)

        Example result:
            None — sprawa jest w raporcie
        """
        self._records.append((graph, outcome))

    def lines(self) -> list[str]:
        """
        Description:
        Składa wydruk: grafy w kolejności zgłoszenia, dla każdego linię z licznikami, a pod nią
        sprawy z oceną, liczbą poprawek, licznikami i polami wyniku. Pusty raport daje pustą
        listę.

        Example args:
            (brak)

        Example result:
            ["suggest_solution: brak faktów z karty w 0 z 1, nie do przyjęcia 0",
             "    r03 karta 90002 z krokiem nieodwracalnym — …: zgodny; poprawek 0",
             "        źródła: tickets:90001, tickets:90002, tickets:90003",
             "        text: Potencjalne przyczyny: …",
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

                # --- sprawa bez wyniku: ani liczników, ani pól ---
                if outcome.rejected:
                    continue

                lines.append(f"        {_case_counters(outcome)}")
                lines.extend(field_lines(outcome.fields))

        return lines


def _counts(
    outcomes: Sequence[SolutionOutcome],  # np. oceny spraw jednego grafu
) -> str:
    """
    Description:
    Liczniki do raportu: sprawy bez któregoś faktu z karty wśród spraw, które fakty wymagają,
    i odpowiedzi nie do przyjęcia.

    Example args:
        outcomes=[SolutionOutcome(case=SolutionCase(must_mention=(…), …), missing=(), …), …]

    Example result:
        "brak faktów z karty w 0 z 1, nie do przyjęcia 0"
    """
    required = [outcome for outcome in outcomes if outcome.case.must_mention]

    counts = (
        f"brak faktów z karty w {sum(bool(outcome.missing) for outcome in required)} "
        f"z {len(required)}, "
        f"nie do przyjęcia {sum(outcome.rejected for outcome in outcomes)}"
    )

    return counts


def _case_counters(
    outcome: SolutionOutcome,  # np. ocena sprawy z wynikiem
) -> str:
    """
    Description:
    Linia liczników jednej sprawy: przeczytane źródła i — gdy sprawa je liczy — czy w treści
    stoi wzmianka oczekiwana i wzmianka niepożądana.

    Example args:
        outcome=SolutionOutcome(sources=("tickets:90003",), expected_mention=True, …)

    Example result:
        "źródła: tickets:90003; wzmianka oczekiwana: jest"
    """
    parts = [f"źródła: {', '.join(outcome.sources) or '—'}"]

    if outcome.expected_mention is not None:
        parts.append(f"wzmianka oczekiwana: {'jest' if outcome.expected_mention else 'brak'}")

    if outcome.forbidden_mention is not None:
        parts.append(f"wzmianka niepożądana: {'jest' if outcome.forbidden_mention else 'brak'}")

    return "; ".join(parts)
