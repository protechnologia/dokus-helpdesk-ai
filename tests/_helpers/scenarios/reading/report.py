"""
Description:
Raport scenariuszy czytania znalezionego materiału: `ReadingReport` zbiera oceny spraw z jednego
przebiegu pytesta i składa wydruk, który pytest pokazuje po testach — liczniki błędów, a pod nimi
każdą sprawę z oceną, licznikami (źródła, nazwane fakty, przyczyny wykluczone, sekcje
oczekiwane i niepożądane, narzędzia kodu) i polami wyniku w całości. Sprawa, w której kod jest
niepożądany, a model po niego sięgnął, jest wyróżniona w linii grafu i przy sprawie.

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `reading_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
- Pola wyniku wypisuje `field_lines()` z helpera wstrzyknięć, wspólna dla raportów
  scenariuszy, więc zmiana wydruku pól dotyczy wszystkich.
"""

from collections.abc import Sequence

from tests._helpers.scenarios.injections import field_lines
from tests._helpers.scenarios.reading.models.reading_outcome import ReadingOutcome


class ReadingReport:
    """
    Description:
    Zbiera oceny spraw ze scenariuszy czytania w jednym przebiegu pytesta i składa z nich wydruk:
    dla grafu linię z licznikami, a pod nią każdą sprawę z oceną, licznikami i polami wyniku
    w całości.

    Do czego:
    Test zalicza zestaw po tym, czy model przeczytał wszystkie znalezione karty, ale czy wynik
    nazywa ich przyczyny, czy uwagi mówią, którą przyczynę wykluczył klient, którą sekcję
    instrukcji model przeczytał i czy w sprawie organizacyjnej sięgał po kod, mówią liczniki,
    a jak to napisał — dopiero treść. Wydruk jest po to, żeby ją przeczytać.

    Flow:
        1. Test dostaje raport przez fixture `reading_report` i woła `record()` raz na sprawę.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            ReadingReport bez zgłoszonych spraw
        """
        self._records: list[tuple[str, ReadingOutcome]] = []

    def record(
        self,
        graph:   str,             # np. "search"
        outcome: ReadingOutcome,  # np. judge_reading_case(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednej sprawy.

        Example args:
            graph="search"
            outcome=ReadingOutcome(case=ReadingCase(case_id="c01", …), unread=(), …)

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
            ["search: nieprzeczytane w 0 z 2, nie do przyjęcia 0",
             "    c01 sam objaw, a znalezione karty niosą trzy przyczyny: zgodny; poprawek 0",
             "        źródła: tickets:90001, tickets:90002, tickets:90003; nazwane 3 z 3: …",
             "        internal_notes: ## Zgłoszenia historyczne",
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
    outcomes: Sequence[ReadingOutcome],  # np. oceny spraw jednego grafu
) -> str:
    """
    Description:
    Liczniki do raportu: sprawy z nieprzeczytanym materiałem wśród spraw, które go wymagają,
    odpowiedzi nie do przyjęcia, a gdy graf ma sprawy bez kodu — te z nich, w których model
    sięgnął po kod.

    Example args:
        outcomes=[ReadingOutcome(case=ReadingCase(must_read=(…), …), unread=(), …), …]

    Example result:
        "nieprzeczytane w 0 z 2, nie do przyjęcia 0, kod niepożądany w 1 z 1"
    """
    required = [outcome for outcome in outcomes if outcome.case.must_read]
    codeless = [outcome for outcome in outcomes if outcome.case.should_not_call_code]

    counts = (
        f"nieprzeczytane w {sum(bool(outcome.unread) for outcome in required)} "
        f"z {len(required)}, "
        f"nie do przyjęcia {sum(outcome.rejected for outcome in outcomes)}"
    )

    # --- graf bez spraw, w których kod jest niepożądany: licznik nic by nie mówił ---
    if not codeless:
        return counts

    needless = sum(outcome.needless_code for outcome in codeless)

    return f"{counts}, kod niepożądany w {needless} z {len(codeless)}"


def _case_counters(
    outcome: ReadingOutcome,  # np. ocena sprawy z wynikiem
) -> str:
    """
    Description:
    Linia liczników jednej sprawy: przeczytane źródła, a gdy sprawa je liczy — fakty nazwane
    w wyniku, przyczyny nazwane w uwagach jako wykluczone, przeczytane sekcje oczekiwane
    i niepożądane; na końcu zawsze wywołania narzędzi kodu, z dopiskiem, gdy w tej sprawie
    każde jest niepożądane.

    Example args:
        outcome=ReadingOutcome(sources=("docs:adm-kancelaria-edoreczenia",), named=("zalog",),
                               read_wanted=("docs:adm-kancelaria-edoreczenia",), …)

    Example result:
        "źródła: docs:adm-kancelaria-edoreczenia; nazwane 1 z 1: zalog; oczekiwane przeczytane
         1 z 1; niepożądane przeczytane 0 z 1; narzędzia kodu: 0"
    """
    case  = outcome.case
    parts = [f"źródła: {', '.join(outcome.sources) or '—'}"]

    if case.should_name:
        named = f": {', '.join(outcome.named)}" if outcome.named else ""
        parts.append(f"nazwane {len(outcome.named)} z {len(case.should_name)}{named}")

    if case.should_exclude:
        parts.append(
            f"wykluczone w uwagach {len(outcome.excluded)} z {len(case.should_exclude)}"
        )

    if case.should_read:
        parts.append(
            f"oczekiwane przeczytane {len(outcome.read_wanted)} z {len(case.should_read)}"
        )

    if case.should_not_read:
        parts.append(
            f"niepożądane przeczytane {len(outcome.read_unwanted)} z {len(case.should_not_read)}"
        )

    code = f"narzędzia kodu: {outcome.code_calls}"
    parts.append(f"{code} (powinno być 0)" if outcome.needless_code else code)

    return "; ".join(parts)
