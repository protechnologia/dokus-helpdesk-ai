"""
Description:
Zestaw scenariuszy „Popraw” (`data/safe/golden/polish.json`) i ocena sprawy przeprowadzonej na
żywym modelu: czy poprawiony tekst zmienił formę notatek, a nie ich treść. Sprawa to notatki
wdrożeniowca z listą słów potocznych, które mają zniknąć, faktów, które mają zostać, i pułapek —
dopisków, które kuszą model, a których w notatkach nie ma. Korzysta z niego test ewaluacyjny
„Popraw” (p. 59), a raport stąd pytest wypisuje po przebiegu.

| co                    | do czego                                                        |
|-----------------------|-----------------------------------------------------------------|
| `polish_sections()`   | sekcje zestawu po nazwie grafu                                  |
| `PolishSection`       | sekcja: wersja zasad stylu i sprawy                             |
| `PolishCase`          | jedna sprawa: notatki, słowa potoczne, fakty i pułapki          |
| `plain()`             | tekst do porównań: małe litery, bez polskich znaków i odstępów |
| `numbers()`           | liczby w tekście, bez numerów listy                             |
| `judge_polish_case()` | ocena jednej sprawy                                             |
| `PolishOutcome`       | wynik oceny: co zostało, co zginęło, co przybyło                |
| `PolishReport`        | raport: `record()` dopisuje sprawę, `lines()` składa wydruk     |

Przykład — notatki „limit to 5 MB, pdf ma 12 MB i sie wywala”:

    outcome = judge_polish_case(
        case    = PolishCase(case_id="s04", phenomenon="…", text="limit to 5 MB…",
                             colloquial=("wywala",), kept=("5 MB", "12 MB"),
                             tempting=("rozdzielczo",)),
        output  = PolishedText(text="1. Prosimy zmniejszyć plik do 5 MB w ciągu 3 dni."),
        retries = 0,
    )

    outcome.lost        -> ("12 MB",)
    outcome.new_numbers -> ("3",)
    outcome.assessment  -> "zgubione: 12 MB; nowe liczby: 3"

Jak sprawa jest oceniana:

1. Słowo potoczne i pułapkę szuka się jako fragmentu w zapisie `plain()`, więc rdzeń „smig”
   znajduje „śmiga” i „śmigać”, a „menu” — „w menu”.
2. Fakt szuka się tak samo: „15 MB” znajduje „15MB”.
3. Nowa liczba to ciąg cyfr w tekście, którego nie ma w notatkach. Numer listy na początku
   linii („1. ”, „2) ”) liczbą nie jest, bo zasady stylu każą pisać kroki listą numerowaną.

O czym pamiętać przy zmianach:

- Liczba zapisana słowem w notatkach („na dwa pliki”), a cyfrą w tekście, wyjdzie jako nowa:
  notatki w zestawie piszą liczby cyframi.
- Raport dostaje się przez fixture `polish_report` z `tests/conftest.py`, jeden na cały
  przebieg; tam też stoi funkcja, która go wypisuje.
"""

import dataclasses
import json
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from tests.helpers_injections import field_lines

POLISH_FILE = Path("data/safe/golden/polish.json")

# Klucz zestawu z metryczką, a nie sekcja grafu.
META_KEY = "meta"

# Litery, których rozkład Unicode nie zdejmuje do litery bez znaku.
EXTRA_LETTERS = str.maketrans({"ł": "l"})

# Numer listy na początku linii: „1. ”, „12) ”.
LIST_NUMBER = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class PolishCase:
    """Jedna sprawa „Popraw” z zestawu: notatki i to, co ma się z nimi stać."""

    case_id:    str              # np. "s01"
    phenomenon: str              # np. "słowa potoczne i liczba w notatkach"
    text:       str              # notatki wdrożeniowca, np. "przesylki juz ida…"
    colloquial: tuple[str, ...]  # rdzenie słów potocznych, które mają zniknąć, np. ("smig",)
    kept:       tuple[str, ...]  # fakty, które mają zostać, np. ("17",)
    tempting:   tuple[str, ...]  # pułapki: dopiski, których nie ma w notatkach, np. ("menu",)

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa sprawy w raporcie: identyfikator i zjawisko.

        Example args:
            (brak)

        Example result:
            "s01 słowa potoczne i liczba w notatkach"
        """
        return f"{self.case_id} {self.phenomenon}"


@dataclasses.dataclass(frozen=True)
class PolishSection:
    """Sekcja zestawu dla grafu „Popraw”: wersja zasad stylu, pod którą napisano sprawy,
    i sprawy."""

    graph:         str                     # np. "polish"
    rules_version: int                     # np. 1 — wersja zestawu domyślnego zasad stylu
    cases:         tuple[PolishCase, ...]  # sprawy w kolejności zestawu


@dataclasses.dataclass(frozen=True)
class PolishOutcome:
    """Ocena jednej sprawy „Popraw”."""

    case:        PolishCase         # sprawa, której dotyczy ocena
    rejected:    bool               # węzeł `respond` nie przyjął odpowiedzi mimo poprawki
    colloquial:  tuple[str, ...]    # słowa potoczne, które zostały w tekście
    lost:        tuple[str, ...]    # fakty z notatek, których w tekście nie ma
    new_numbers: tuple[str, ...]    # liczby z tekstu, których nie ma w notatkach
    added:       tuple[str, ...]    # pułapki, które trafiły do tekstu
    retries:     int                # poprawki odpowiedzi od węzła `respond`
    fields:      Mapping[str, Any]  # pola wyniku do raportu; puste, gdy wyniku nie ma

    @property
    def assessment(self) -> str:
        """
        Description:
        Ocena jednym zdaniem dla raportu: „zgodny” albo lista tego, co poszło źle.

        Example args:
            (brak)

        Example result:
            "potoczne: smig; nowe liczby: 3"
        """
        # --- odpowiedź nie do przyjęcia: tekstu nie ma ---
        if self.rejected:
            return "ODPOWIEDŹ NIE DO PRZYJĘCIA"

        problems = [
            f"{name}: {', '.join(found)}"
            for name, found in (
                ("potoczne",    self.colloquial),
                ("zgubione",    self.lost),
                ("nowe liczby", self.new_numbers),
                ("dopisane",    self.added),
            )
            if found
        ]

        return "; ".join(problems) if problems else "zgodny"


def polish_sections(
    path: Path = POLISH_FILE,  # np. Path("data/safe/golden/polish.json")
) -> dict[str, PolishSection]:
    """
    Description:
    Czyta zestaw scenariuszy „Popraw” i oddaje jego sekcje po nazwie grafu, bez metryczki.

    Example args:
        path=Path("data/safe/golden/polish.json")

    Example result:
        {"polish": PolishSection(graph="polish", rules_version=1,
                                 cases=(PolishCase(case_id="s01", …), …))}
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    sections = {
        graph: PolishSection(
            graph         = graph,
            rules_version = body["rules_version"],
            cases         = tuple(_case_from(entry) for entry in body["cases"]),
        )
        for graph, body in raw.items()
        if graph != META_KEY
    }

    return sections


def _case_from(
    entry: Mapping[str, Any],  # np. {"id": "s01", "phenomenon": "…", "input": "…", …}
) -> PolishCase:
    """
    Description:
    Zamienia wpis sprawy z zestawu na `PolishCase`; nazwy pól zestawu są krótsze.

    Example args:
        entry={"id": "s01", "phenomenon": "…", "input": "przesylki…", "colloquial": ["smig"],
               "kept": ["17"], "tempting": []}

    Example result:
        PolishCase(case_id="s01", text="przesylki…", colloquial=("smig",), kept=("17",), …)
    """
    case = PolishCase(
        case_id    = entry["id"],
        phenomenon = entry["phenomenon"],
        text       = entry["input"],
        colloquial = tuple(entry["colloquial"]),
        kept       = tuple(entry["kept"]),
        tempting   = tuple(entry["tempting"]),
    )

    return case


def plain(
    text: str,  # np. "Teraz wszystko śmiga, plik ma 15 MB."
) -> str:
    """
    Description:
    Zapisuje tekst do porównań: małe litery, bez polskich znaków i bez odstępów. Notatki bywają
    pisane bez polskich znaków, a tekst po poprawce — z nimi; fakt „15 MB” bywa zapisany razem.

    Example args:
        text="Teraz wszystko śmiga, plik ma 15 MB."

    Example result:
        "terazwszystkosmiga,plikma15mb."
    """
    folded  = text.casefold().translate(EXTRA_LETTERS)
    letters = unicodedata.normalize("NFKD", folded)
    bare    = "".join(char for char in letters if not unicodedata.combining(char))

    return "".join(bare.split())


def numbers(
    text: str,  # np. "1. Zmniejsz plik do 5 MB.\n2. Wyślij ponownie po 3 dniach."
) -> set[str]:
    """
    Description:
    Ciągi cyfr w tekście, bez numerów listy na początku linii.

    Example args:
        text="1. Zmniejsz plik do 5 MB.\\n2. Wyślij ponownie po 3 dniach."

    Example result:
        {"5", "3"}
    """
    return set(re.findall(r"\d+", LIST_NUMBER.sub("", text)))


def judge_polish_case(
    case:    PolishCase,        # np. PolishCase(case_id="s04", …)
    output:  BaseModel | None,  # np. PolishedText(text="…"); None — `respond` nie przyjął
    retries: int,               # np. 0 — poprawki odpowiedzi od węzła `respond`
) -> PolishOutcome:
    """
    Description:
    Ocenia jedną sprawę „Popraw”: które słowa potoczne zostały, które fakty zginęły, jakie
    liczby przybyły i które pułapki trafiły do tekstu; brak wyniku zapisuje jako odpowiedź nie
    do przyjęcia.

    Example args:
        case=PolishCase(case_id="s04", text="limit to 5 MB…", colloquial=("wywala",),
                        kept=("5 MB", "12 MB"), tempting=("rozdzielczo",), …)
        output=PolishedText(text="Dzień dobry, …")
        retries=0

    Example result:
        PolishOutcome(case=PolishCase(case_id="s04", …), rejected=False, colloquial=(),
                      lost=("12 MB",), new_numbers=("3",), added=(), retries=0, fields={…})
    """
    # --- brak wyniku: węzeł `respond` nie przyjął odpowiedzi mimo poprawki ---
    if output is None:
        rejected = PolishOutcome(
            case        = case,
            rejected    = True,
            colloquial  = (),
            lost        = (),
            new_numbers = (),
            added       = (),
            retries     = retries,
            fields      = {},
        )

        return rejected

    fields = output.model_dump(mode="json")
    text   = plain(fields["text"])

    outcome = PolishOutcome(
        case        = case,
        rejected    = False,
        colloquial  = tuple(word for word in case.colloquial if plain(word) in text),
        lost        = tuple(fact for fact in case.kept if plain(fact) not in text),
        new_numbers = tuple(sorted(numbers(fields["text"]) - numbers(case.text), key=int)),
        added       = tuple(word for word in case.tempting if plain(word) in text),
        retries     = retries,
        fields      = fields,
    )

    return outcome


class PolishReport:
    """
    Description:
    Zbiera oceny spraw ze scenariuszy „Popraw” w jednym przebiegu pytesta i składa z nich
    wydruk: dla grafu linię z licznikami, a pod nią każdą sprawę z oceną i poprawionym tekstem
    w całości.

    Do czego:
    Test łapie słowa z list, a o tym, czy tekst nie dodał kroku albo obietnicy, której nie ma na
    żadnej liście, mówi dopiero sam tekst. Wydruk jest po to, żeby go przeczytać.

    Flow:
        1. Test dostaje raport przez fixture `polish_report` i woła `record()` raz na sprawę.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            PolishReport bez zgłoszonych spraw
        """
        self._records: list[tuple[str, PolishOutcome]] = []

    def record(
        self,
        graph:   str,            # np. "polish"
        outcome: PolishOutcome,  # np. judge_polish_case(…)
    ) -> None:
        """
        Description:
        Dopisuje do raportu ocenę jednej sprawy.

        Example args:
            graph="polish"
            outcome=PolishOutcome(case=PolishCase(case_id="s01", …), …)

        Example result:
            None — sprawa jest w raporcie
        """
        self._records.append((graph, outcome))

    def lines(self) -> list[str]:
        """
        Description:
        Składa wydruk: grafy w kolejności zgłoszenia, dla każdego linię z licznikami, a pod nią
        sprawy z oceną, liczbą poprawek i poprawionym tekstem. Pusty raport daje pustą listę.

        Example args:
            (brak)

        Example result:
            ["polish: potoczne w 0 z 4, zgubione fakty w 0 z 4, nowe liczby w 0 z 4, "
             "dopisane w 0 z 4, nie do przyjęcia 0",
             "    s01 słowa potoczne i liczba w notatkach: zgodny; poprawek 0",
             "        text: Dzień dobry,",
             …]
        """
        graphs = list(dict.fromkeys(graph for graph, _ in self._records))
        lines: list[str] = []

        for graph in graphs:
            outcomes = [outcome for name, outcome in self._records if name == graph]
            total    = len(outcomes)

            lines.append(
                f"{graph}: "
                f"potoczne w {sum(bool(outcome.colloquial) for outcome in outcomes)} z {total}, "
                f"zgubione fakty w {sum(bool(outcome.lost) for outcome in outcomes)} z {total}, "
                f"nowe liczby w {sum(bool(outcome.new_numbers) for outcome in outcomes)} "
                f"z {total}, "
                f"dopisane w {sum(bool(outcome.added) for outcome in outcomes)} z {total}, "
                f"nie do przyjęcia {sum(outcome.rejected for outcome in outcomes)}"
            )

            for outcome in outcomes:
                lines.append(
                    f"    {outcome.case.label}: {outcome.assessment}; poprawek {outcome.retries}"
                )
                lines.extend(field_lines(outcome.fields))

        return lines
