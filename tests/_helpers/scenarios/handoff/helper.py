"""
Description:
Zestaw scenariuszy przekazania sprawy (`data/safe/golden/handoff.json`) i ocena sprawy
przeprowadzonej na żywym modelu: czy wiadomość trzyma układ z przykładu, niesie fakty z wątku
i ostrzeżenie, a niczego nie dopisuje. Sprawa to zgłoszenie z listą faktów, które mają zostać,
rdzeni ostrzeżenia i pułapek, czyli dopisków, które kuszą model. Korzysta z niego test ewaluacyjny
przekazania (p. 59). Modele zestawu i oceny leżą w `models/`, a raport, który pytest wypisuje po
przebiegu, w `report.py`.

| co                     | do czego                                                     |
|------------------------|--------------------------------------------------------------|
| `handoff_sections()`   | sekcje zestawu po nazwie grafu                               |
| `layout_problems()`    | czym układ wiadomości różni się od przykładu                 |
| `judge_handoff_case()` | ocena jednej sprawy                                          |

Przykład — zgłoszenie o braku UPO dla 40 pism:

    outcome = judge_handoff_case(
        case    = HandoffCase(case_id="h07", phenomenon="…", text="ZGŁOSZENIE 90307…",
                              kept=("UPO", "40"), warning=(), tempting=("zrzut ekranu",)),
        output  = Proposal(text="Dzień dobry.\n\nBrakuje UPO.\n\nSprawdzimy to w 3 dni.\n\n"
                                "Pozdrawiam.", internal_notes=""),
        retries = 0,
    )

    outcome.lost        -> ("40",)
    outcome.new_numbers -> ("3",)
    outcome.promised    -> ("sprawdzimy",)
    outcome.layout      -> ("przedostatni akapit nie mówi o przekazaniu",)

Jak sprawa jest oceniana:

1. Fakt, pułapkę i rdzeń ostrzeżenia szuka się jako fragmentu w zapisie `plain()` z helpera
   „Popraw”, więc wielkość liter, polskie znaki i odstępy nie mają znaczenia.
2. Fakty są wymagane wszystkie, a z rdzeni ostrzeżenia wystarczy jeden, bo model pisze to różnie.
3. Obietnice i fragmenty przykładu sprawdza się w każdej sprawie, także bez pułapek.
4. Znaczników wiadomość nie musi powtarzać: podsumowanie może się bez nich obyć. Liczy się tylko
   napis w klamrach, który nie jest znacznikiem ani placeholderem z promptu.

O czym pamiętać przy zmianach:

- Fragmenty przykładu stoją w `constants.py`: po zmianie przykładu w `respond_tool.md` test bez
  modelu kończy się błędem, dopóki ich nie poprawisz.
- Listy łapią tylko to, co przewidział autor sprawy: zgadywaną przyczynę spoza pułapek pokaże
  dopiero wiadomość, którą raport wypisuje w całości.
"""

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from tests._helpers.markers import malformed_markers
from tests._helpers.scenarios.handoff.constants import (
    EXAMPLE_PHRASES,
    FAREWELL,
    GREETING,
    HANDOFF_FILE,
    HANDOVER_WORDS,
    META_KEY,
    MIN_PARAGRAPHS,
    PROMISES,
)
from tests._helpers.scenarios.handoff.models.handoff_case import HandoffCase
from tests._helpers.scenarios.handoff.models.handoff_outcome import HandoffOutcome
from tests._helpers.scenarios.handoff.models.handoff_section import HandoffSection
from tests._helpers.scenarios.polish import numbers, plain


def handoff_sections(
    path: Path = HANDOFF_FILE,  # np. Path("data/safe/golden/handoff.json")
) -> dict[str, HandoffSection]:
    """
    Description:
    Czyta zestaw scenariuszy przekazania i oddaje jego sekcje po nazwie grafu, bez metryczki.

    Example args:
        path=Path("data/safe/golden/handoff.json")

    Example result:
        {"suggest_handoff": HandoffSection(graph="suggest_handoff",
                                           cases=(HandoffCase(case_id="h01", …), …))}
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    sections = {
        graph: HandoffSection(
            graph = graph,
            cases = tuple(_case_from(entry) for entry in body["cases"]),
        )
        for graph, body in raw.items()
        if graph != META_KEY
    }

    return sections


def _case_from(
    entry: Mapping[str, Any],  # np. {"id": "h01", "phenomenon": "…", "input": "ZGŁOSZENIE…", …}
) -> HandoffCase:
    """
    Description:
    Zamienia wpis sprawy z zestawu na `HandoffCase`; nazwy pól zestawu są krótsze.

    Example args:
        entry={"id": "h04", "phenomenon": "…", "input": "ZGŁOSZENIE 90304…", "kept": ["ePUAP"],
               "warning": ["nie ponawia"], "tempting": []}

    Example result:
        HandoffCase(case_id="h04", text="ZGŁOSZENIE 90304…", kept=("ePUAP",), …)
    """
    case = HandoffCase(
        case_id    = entry["id"],
        phenomenon = entry["phenomenon"],
        text       = entry["input"],
        kept       = tuple(entry["kept"]),
        warning    = tuple(entry["warning"]),
        tempting   = tuple(entry["tempting"]),
    )

    return case


def layout_problems(
    text: str,  # np. "Dzień dobry.\n\nNie działa import.\n\nPrzekazujemy sprawę.\n\nPozdrawiam."
) -> tuple[str, ...]:
    """
    Description:
    Mówi, czym układ wiadomości różni się od przykładu: powitanie i pożegnanie w osobnych
    akapitach, co najmniej cztery akapity, a przedostatni mówi o przekazaniu sprawy.

    Example args:
        text="Dzień dobry, nie działa import. Przekazujemy sprawę."

    Example result:
        ("pierwszy akapit to nie powitanie", "ostatni akapit to nie pożegnanie",
         "akapitów 1 zamiast co najmniej 4", "przedostatni akapit nie mówi o przekazaniu")
    """
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text.strip())]
    handover   = plain(paragraphs[-2]) if len(paragraphs) > 1 else ""

    checks = (
        (paragraphs[0] == GREETING,   "pierwszy akapit to nie powitanie"),
        (paragraphs[-1] == FAREWELL,  "ostatni akapit to nie pożegnanie"),
        (
            len(paragraphs) >= MIN_PARAGRAPHS,
            f"akapitów {len(paragraphs)} zamiast co najmniej {MIN_PARAGRAPHS}",
        ),
        (
            any(word in handover for word in HANDOVER_WORDS),
            "przedostatni akapit nie mówi o przekazaniu",
        ),
    )

    return tuple(problem for passed, problem in checks if not passed)


def judge_handoff_case(
    case:    HandoffCase,       # np. HandoffCase(case_id="h04", …)
    output:  BaseModel | None,  # np. Proposal(text="…", internal_notes=""); None — nie przyjął
    retries: int,               # np. 0 — poprawki odpowiedzi od węzła `respond`
) -> HandoffOutcome:
    """
    Description:
    Ocenia jedną sprawę przekazania: układ, zgubione fakty i ostrzeżenie, nowe liczby, pułapki,
    obietnice, treść przykładu i przekręcone znaczniki; brak wyniku zapisuje jako odpowiedź nie
    do przyjęcia.

    Example args:
        case=HandoffCase(case_id="h07", text="ZGŁOSZENIE 90307…", kept=("UPO", "40"), …)
        output=Proposal(text="Dzień dobry.\\n\\nBrakuje UPO.\\n\\nPrzekazujemy.\\n\\nPozdrawiam.",
                        internal_notes="")
        retries=0

    Example result:
        HandoffOutcome(case=HandoffCase(case_id="h07", …), rejected=False, layout=(),
                       lost=("40",), warning_lost=False, new_numbers=(), added=(), promised=(),
                       copied=(), malformed=(), retries=0, fields={…})
    """
    # --- brak wyniku: węzeł `respond` nie przyjął odpowiedzi mimo poprawki ---
    if output is None:
        rejected = HandoffOutcome(
            case         = case,
            rejected     = True,
            layout       = (),
            lost         = (),
            warning_lost = False,
            new_numbers  = (),
            added        = (),
            promised     = (),
            copied       = (),
            malformed    = (),
            retries      = retries,
            fields       = {},
        )

        return rejected

    fields = output.model_dump(mode="json")
    text   = plain(fields["text"])

    outcome = HandoffOutcome(
        case         = case,
        rejected     = False,
        layout       = layout_problems(fields["text"]),
        lost         = tuple(fact for fact in case.kept if plain(fact) not in text),
        warning_lost = bool(case.warning) and not any(plain(root) in text for root in case.warning),
        new_numbers  = tuple(sorted(numbers(fields["text"]) - numbers(case.text), key=int)),
        added        = tuple(word for word in case.tempting if plain(word) in text),
        promised     = tuple(word for word in PROMISES if plain(word) in text),
        copied       = tuple(phrase for phrase in EXAMPLE_PHRASES if plain(phrase) in text),
        malformed    = tuple(malformed_markers(fields["text"])),
        retries      = retries,
        fields       = fields,
    )

    return outcome
