"""
Description:
Zestaw scenariuszy „Popraw” (`data/safe/golden/polish.json`) i ocena sprawy przeprowadzonej na
żywym modelu: czy poprawiony tekst zmienił formę notatek, a nie ich treść. Sprawa to notatki
wdrożeniowca z listą słów potocznych, które mają zniknąć, faktów, które mają zostać, i pułapek —
dopisków, które kuszą model, a których w notatkach nie ma. Korzysta z niego test ewaluacyjny
„Popraw” (p. 59). Modele zestawu i oceny leżą w `models/`, a raport, który pytest wypisuje po
przebiegu, w `report.py`.

| co                    | do czego                                                        |
|-----------------------|-----------------------------------------------------------------|
| `polish_sections()`   | sekcje zestawu po nazwie grafu                                  |
| `plain()`             | tekst do porównań: małe litery, bez polskich znaków i odstępów |
| `numbers()`           | liczby w tekście, bez numerów listy                             |
| `judge_polish_case()` | ocena jednej sprawy                                             |

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
"""

import json
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from tests._helpers.markers import lost_markers, malformed_markers
from tests._helpers.scenarios.polish.constants import (
    EXTRA_LETTERS,
    LIST_NUMBER,
    META_KEY,
    POLISH_FILE,
)
from tests._helpers.scenarios.polish.models.polish_case import PolishCase
from tests._helpers.scenarios.polish.models.polish_outcome import PolishOutcome
from tests._helpers.scenarios.polish.models.polish_section import PolishSection


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
        case         = case,
        rejected     = False,
        colloquial   = tuple(word for word in case.colloquial if plain(word) in text),
        lost         = tuple(fact for fact in case.kept if plain(fact) not in text),
        new_numbers  = tuple(sorted(numbers(fields["text"]) - numbers(case.text), key=int)),
        added        = tuple(word for word in case.tempting if plain(word) in text),
        retries      = retries,
        fields       = fields,
        lost_markers = tuple(lost_markers(case.text, fields["text"])),
        malformed    = tuple(malformed_markers(fields["text"])),
    )

    return outcome
