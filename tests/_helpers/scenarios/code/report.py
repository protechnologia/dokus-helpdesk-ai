"""
Description:
Raport scenariuszy cytowania kodu: `CodeReport` zbiera oceny spraw z jednego przebiegu
pytesta i składa wydruk, który pytest pokazuje po testach — liczniki błędów, a pod nimi każdą
sprawę z oceną, licznikami (przyczyny z kodu, spisy katalogu, nazwy w uwagach, fragment
wykluczony przez wątek) i uwagami w całości.

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `code_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
- Pola wyniku wypisuje `field_lines()` z helpera wstrzyknięć, wspólna dla raportów
  scenariuszy, więc zmiana wydruku pól dotyczy wszystkich.
"""

from collections.abc import Sequence

from tests._helpers.scenarios.code.models.code_outcome import CodeOutcome
from tests._helpers.scenarios.injections import field_lines


class CodeReport:
    """
    Description:
    Zbiera oceny spraw ze scenariuszy cytowania kodu w jednym przebiegu pytesta i składa z nich
    wydruk: dla grafu linię z licznikami błędów, a pod nią każdą sprawę z oceną, licznikami
    i uwagami dla wdrożeniowca w całości.

    Do czego:
    Test zalicza zestaw po cytowaniach przyczyny i po tym, czy model cytował linie, które
    przeczytał. Czy sięgnął po spis katalogu, czy nazwał plik widoczny tylko w spisie, czy przy
    wątku nie wskazał przyczyny, którą odpowiedzi klienta wykluczają, i czy uwagi odróżniają stan
    kodu od instalacji klienta, mówią liczniki i treść uwag — wydruk jest po to, żeby je przeczytać.

    Flow:
        1. Test dostaje raport przez fixture `code_report` i woła `record()` raz na sprawę.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            CodeReport bez zgłoszonych spraw
        """
        self._records: list[tuple[str, CodeOutcome]] = []

    def record(
        self,
        graph:   str,            # np. "search"
        outcome: CodeOutcome,  # np. judge_code_case(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednej sprawy.

        Example args:
            graph="search"
            outcome=CodeOutcome(case=CodeCase(case_id="k01", …), cause_files=(…), …)

        Example result:
            None — sprawa jest w raporcie
        """
        self._records.append((graph, outcome))

    def lines(self) -> list[str]:
        """
        Description:
        Składa wydruk: grafy w kolejności zgłoszenia, dla każdego linię z licznikami, a pod nią
        sprawy z oceną, liczbą poprawek, licznikami sprawy i polami wyniku. Pusty raport daje
        pustą listę.

        Example args:
            (brak)

        Example result:
            ["search: bez pliku przyczyny w 0 z 1, przyczyna z luźnego pliku w 0 z 1, cytowania "
             "nieodczytane w 0 z 4, nie do przyjęcia 0",
             "    k01 komunikat tylko w kodzie: zgodny; poprawek 0",
             "        przyczyny z kodu: src/lib/Urzad/Szablony/RejestrSzablonow.php; spisów 1; "
             "w uwagach: wezwanie_stare",
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

                # --- odpowiedź nie do przyjęcia: liczników nie ma z czego liczyć ---
                if not outcome.rejected:
                    lines.append(f"        {_case_counters(outcome)}")

                lines.extend(field_lines(outcome.fields))

        return lines


def _counts(
    outcomes: Sequence[CodeOutcome],  # np. oceny spraw jednego grafu
) -> str:
    """
    Description:
    Liczniki błędów do raportu: brak pliku przyczyny wśród spraw, które go wymagają, przyczyna
    z luźnego pliku wśród spraw, w których komunikatu nie ma w kodzie, sprawy z cytowaniem linii
    nieodczytanych i odpowiedzi nie do przyjęcia.

    Example args:
        outcomes=[CodeOutcome(case=CodeCase(must_quote_as_cause=("…",), …), …), …]

    Example result:
        "bez pliku przyczyny w 1 z 1, przyczyna z luźnego pliku w 0 z 1, cytowania nieodczytane
         w 0 z 4, nie do przyjęcia 0"
    """
    required = [outcome for outcome in outcomes if outcome.case.must_quote_as_cause]
    nowhere  = [outcome for outcome in outcomes if outcome.case.must_not_quote_any_cause]

    counts = (
        f"bez pliku przyczyny w {sum(bool(o.missing_causes) for o in required)} "
        f"z {len(required)}, "
        f"przyczyna z luźnego pliku w {sum(bool(o.stray_causes) for o in nowhere)} "
        f"z {len(nowhere)}, "
        f"cytowania nieodczytane w {sum(bool(o.unread) for o in outcomes)} z {len(outcomes)}, "
        f"nie do przyjęcia {sum(o.rejected for o in outcomes)}"
    )

    return counts


def _case_counters(
    outcome: CodeOutcome,  # np. ocena sprawy z wynikiem
) -> str:
    """
    Description:
    Liczniki jednej sprawy w jednej linii: pliki zacytowane jako przyczyna i wywołania spisu
    katalogu zawsze, a nazwy w uwagach i przyczynę wykluczoną przez wątek tylko w sprawie, która
    je liczy.

    Example args:
        outcome=CodeOutcome(case=CodeCase(notes_should_include=("wezwanie_stare",), …),
                              listings=1, …)

    Example result:
        "przyczyny z kodu: src/lib/Urzad/Szablony/RejestrSzablonow.php; spisów 1; w uwagach:
         wezwanie_stare"
    """
    parts = [
        f"przyczyny z kodu: {', '.join(outcome.cause_files) or '—'}",
        f"spisów {outcome.listings}",
    ]

    # --- sprawa liczy nazwy, które uwagi mają wymienić ---
    if outcome.case.notes_should_include:
        missing  = outcome.missing_in_notes
        included = [name for name in outcome.case.notes_should_include if name not in missing]
        parts.append(
            f"w uwagach: {', '.join(included) or '—'}"
            + (f", brak: {', '.join(missing)}" if missing else "")
        )

    # --- sprawa z wątkiem, który wyklucza jedną z przyczyn ---
    if outcome.case.should_not_quote_as_cause is not None:
        fragment = outcome.case.should_not_quote_as_cause.key
        quoted   = "tak" if outcome.ruled_out_cause_quoted else "nie"
        parts.append(f"wykluczona przez wątek przyczyna {fragment} zacytowana: {quoted}")

    return "; ".join(parts)
