"""
Description:
Wzorce usługi `anonymizer` w testach: tekst po zamianie miejsc z jednego wariantu, zamiana
wszystkimi wzorcami w kształcie funkcji anonimizującej z golden setu i odczyt pomiaru wzorców:
rodzaje ponad próg, ich przecieki i zniszczona wiedza, nazwane rodzajem z numerem.
"""

from collections.abc import Callable, Mapping
from pathlib import Path

from anonymizer_app.models.found import Found
from anonymizer_app.steps.replace_patterns import replace_patterns
from tests._helpers.golden_anonymization import AnonymizationMeasurement, anonymization_set
from tests._helpers.patterns.constants import PATTERN_KINDS

# Wariant wzorca: przyjmuje tekst i zwraca miejsca danych.
Variant = Callable[[str], list[Found]]


def replaced_by(
    variant: Variant,  # np. pesel.find_pesel_with_error_after_label
    text:    str,      # np. "PESEL 85030512843"
) -> str:
    """
    Description:
    Zamienia na znaczniki miejsca, które zwrócił jeden wariant, i nic więcej. Test wariantu widzi
    wtedy wynik w tym samym zapisie co tabela przykładów w docstringu wzorca.

    Example args:
        variant=pesel.find_pesel_with_error_after_label
        text="PESEL 85030512843"

    Example result:
        "PESEL {PESEL}"
    """
    result = text

    # Od końca tekstu, żeby zamiana nie przesuwała miejsc, które czekają na swoją kolej.
    for found in sorted(variant(text), key=lambda found: found.start, reverse=True):
        result = f"{result[:found.start]}{{{found.kind}}}{result[found.end:]}"

    return result


async def anonymize_with_patterns(
    text: str,  # np. "PESEL 85030512840, tel. 600 100 200"
) -> str:
    """
    Description:
    Zamiana wszystkimi wzorcami w kształcie funkcji, którą mierzy golden set anonimizatora
    (`measure_anonymization()` woła ją z `await`).

    Example args:
        text="PESEL 85030512840, tel. 600 100 200"

    Example result:
        "PESEL {PESEL}, tel. {TELEFON}"
    """
    return replace_patterns(text)


def kinds_over_threshold(
    measurement: AnonymizationMeasurement,  # np. pomiar zestawu zmyślonego
    max_leaks:   Mapping[str, int],         # np. MAX_LEAKS_SAFE
) -> dict[str, str]:
    """
    Description:
    Rodzaje od wzorców, w których przecieków jest więcej, niż pozwala próg; rodzaj bez progu ma
    próg zero. Imion i nazwisk nie liczy, bo wzorce ich nie łapią.

    Example args:
        measurement=AnonymizationMeasurement(leaks={"ADRES": KindCount(found=3, total=15), …}, …)
        max_leaks={"ADRES": 2}

    Example result:
        {"ADRES": "3 z 15 (próg 2)"}
    """
    over = {
        kind: f"{count.found} z {count.total} (próg {max_leaks.get(kind, 0)})"
        for kind, count in measurement.leaks.items()
        if kind in PATTERN_KINDS and count.found > max_leaks.get(kind, 0)
    }

    return over


def leaked_fragments(
    measurement: AnonymizationMeasurement,  # np. pomiar próbki korpusu
    kinds:       Mapping[str, str],         # np. wynik kinds_over_threshold()
) -> list[str]:
    """
    Description:
    Przecieki podanych rodzajów z przypadkiem, nazwane jak w ocenie golden setu: przy próbce
    korpusu rodzajem z numerem, bez treści.

    Example args:
        measurement=AnonymizationMeasurement(…)
        kinds={"TELEFON": "1 z 28 (próg 0)"}

    Example result:
        ["u14: TELEFON nr 2"]
    """
    leaked = [
        f"{outcome.case.case_id}: {fragment.shown(outcome.case.synthetic)}"
        for outcome in measurement.outcomes
        for fragment in outcome.leaked
        if fragment.kind in kinds
    ]

    return leaked


def destroyed_fragments(
    measurement: AnonymizationMeasurement,  # np. pomiar zestawu zmyślonego
) -> list[str]:
    """
    Description:
    Zniszczona wiedza z przypadkiem, nazwana jak w ocenie golden setu.

    Example args:
        measurement=AnonymizationMeasurement(…)

    Example result:
        ["s16: NUMER „8443”"]
    """
    destroyed = [
        f"{outcome.case.case_id}: {fragment.shown(outcome.case.synthetic)}"
        for outcome in measurement.outcomes
        for fragment in outcome.destroyed
    ]

    return destroyed


def removed_kinds(
    path: Path,  # np. Path("data/safe/golden/anonymization.json")
) -> set[str]:
    """
    Description:
    Rodzaje danych, które stoją w zestawie golden setu.

    Example args:
        path=Path("data/safe/golden/anonymization.json")

    Example result:
        {"IMIĘ", "NAZWISKO", "PESEL", …}
    """
    return {fragment.kind for case in anonymization_set(path).cases for fragment in case.remove}
