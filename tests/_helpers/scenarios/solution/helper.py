"""
Description:
Zestaw scenariuszy rozwiązania (`data/safe/golden/solution.json`) i ocena sprawy przeprowadzonej
na żywym modelu: czy treść dla klienta w wariancie `suggest_solution` niesie fakty z materiału —
zastrzeżenie i krok nieodwracalny z karty historycznej sprawy — i czy nie każe powtarzać kroku,
który wątek pokazuje jako już wykonany. Narzędzia to atrapy, a karty sprawy mogą mieć zmienione
pola. Korzysta z niego test ewaluacyjny rozwiązania (p. 59). Modele zestawu i oceny leżą
w `models/`, a raport, który pytest wypisuje po przebiegu, w `report.py`.

| co                      | do czego                                                     |
|-------------------------|--------------------------------------------------------------|
| `solution_sections()`   | sekcje zestawu po nazwie grafu                               |
| `case_cards()`          | wbudowane karty atrap ze zmianami sprawy                     |
| `case_tools()`          | narzędzia sprawy: atrapy, a odczyt kart na kartach sprawy    |
| `cards_text()`          | cała treść kart sprawy w jednym tekście                      |
| `ticket_subject()`      | linia tematu zgłoszenia                                      |
| `mentions()`            | czy fakt (którykolwiek wariant) stoi w tekście               |
| `mentions_all()`        | czy wszystkie fakty stoją w tekście naraz                    |
| `question_marks()`      | ile pytań stoi w tekście, bez cytatów i adresów              |
| `judge_solution_case()` | ocena jednej sprawy                                          |

Przykład — karta niesie krok nieodwracalny, a treść dla klienta gubi jego nieodwracalność:

    outcome = judge_solution_case(
        case    = SolutionCase(case_id="r03", must_mention=(("ponowne pobr",),
                               ("nieodwracaln", "nie da się usunąć")), …),
        output  = Proposal(text="… Prosimy nie uruchamiać ponownego pobrania. …", …),
        sources = ("tickets:90002",),
        retries = 0,
    )

    outcome.missing    -> ("nieodwracaln",)
    outcome.assessment -> "BRAK W TREŚCI: nieodwracaln"

O czym pamiętać przy zmianach:

- Fakty porównuje się zapisem `plain()` helpera „Popraw”: bez wielkich liter, polskich znaków
  i odstępów, więc wariant „nie da się usunąć” znajduje „Nie da sie usunac”.
- Liczy się wyłącznie pole `text` — treść dla klienta. Uwagi dla wdrożeniowca idą do raportu,
  ale faktu nie spełniają: wdrożeniowiec nie wyśle ich klientowi. Tak samo pytania: licznik
  liczy znaki zapytania tylko w treści dla klienta, bez cytatów „…” i adresów.
- Zmiany kart przechodzą walidację `ParsedTicket`, więc literówka w nazwie pola kończy się
  błędem przy budowie narzędzi, a nie cichą kartą bez zmiany.
"""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.agent_tools import AgentTool
from app.agent_tools.tickets.fake_tickets import default_cards
from app.core_model.tickets.parsed_ticket import ParsedTicket
from tests._helpers.fake_tools import fake_agent_tools, fake_agent_tools_with_tickets
from tests._helpers.scenarios.polish import plain
from tests._helpers.scenarios.solution.constants import META_KEY, NOT_A_QUESTION, SOLUTION_FILE
from tests._helpers.scenarios.solution.models.solution_case import Fact, SolutionCase
from tests._helpers.scenarios.solution.models.solution_outcome import SolutionOutcome
from tests._helpers.scenarios.solution.models.solution_section import SolutionSection


def solution_sections(
    path: Path = SOLUTION_FILE,  # np. Path("data/safe/golden/solution.json")
) -> dict[str, SolutionSection]:
    """
    Description:
    Czyta zestaw scenariuszy rozwiązania i oddaje jego sekcje po nazwie grafu, bez metryczki.

    Example args:
        path=Path("data/safe/golden/solution.json")

    Example result:
        {"suggest_solution": SolutionSection(graph="suggest_solution",
                                             cases=(SolutionCase(case_id="r01", …), …))}
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    sections = {
        graph: SolutionSection(
            graph = graph,
            cases = tuple(_case_from(entry) for entry in body["cases"]),
        )
        for graph, body in raw.items()
        if graph != META_KEY
    }

    return sections


def _case_from(
    entry: Mapping[str, Any],  # np. {"id": "r03", "must_mention": [["nieodwracaln"]], …}
) -> SolutionCase:
    """
    Description:
    Zamienia wpis sprawy z zestawu na `SolutionCase`. Pole, którego wpis nie ma, znaczy, że
    sprawa go nie sprawdza: brak zmian kart albo pusta lista faktów.

    Example args:
        entry={"id": "r03", "phenomenon": "…", "card_changes": {"90002": {"solution": "…"}},
               "must_mention": [["ponowne pobr"], ["nieodwracaln"]], "input": "ZGŁOSZENIE…"}

    Example result:
        SolutionCase(case_id="r03", phenomenon="…", text="ZGŁOSZENIE…",
                     card_changes={"90002": {"solution": "…"}},
                     must_mention=(("ponowne pobr",), ("nieodwracaln",)), should_mention=(),
                     should_not_mention=())
    """
    case = SolutionCase(
        case_id            = entry["id"],
        phenomenon         = entry["phenomenon"],
        text               = entry["input"],
        card_changes       = entry.get("card_changes", {}),
        must_mention       = _facts(entry.get("must_mention", ())),
        should_mention     = _facts(entry.get("should_mention", ())),
        should_not_mention = _facts(entry.get("should_not_mention", ())),
    )

    return case


def _facts(
    raw: Sequence[Sequence[str]],  # np. [["ręczn"], ["operator"]]
) -> tuple[Fact, ...]:
    """
    Description:
    Zamienia listę faktów z zestawu (każdy to lista wariantów) na krotki.

    Example args:
        raw=[["ręczn"], ["operator"]]

    Example result:
        (("ręczn",), ("operator",))
    """
    return tuple(tuple(variants) for variants in raw)


def case_cards(
    case: SolutionCase,  # np. SolutionCase(card_changes={"90002": {"solution": "…"}}, …)
) -> list[ParsedTicket]:
    """
    Description:
    Wbudowane karty atrap zgłoszeń z polami podmienionymi według `card_changes` sprawy; karta,
    której zmiany nie dotyczą, zostaje bez zmian. Każda zmieniona karta przechodzi walidację.

    Example args:
        case=SolutionCase(card_changes={"90002": {"solution": "Usunięto plik blokady; …"}}, …)

    Example result:
        [ParsedTicket(ticket_id="90001", …), ParsedTicket(ticket_id="90002",
         solution="Usunięto plik blokady; …"), …]

    Raises:
        ValidationError: zmiana nazywa pole, którego karta nie ma, albo daje złą wartość
    """
    cards = [
        ParsedTicket.model_validate(
            {**card.model_dump(), **case.card_changes.get(card.ticket_id, {})}
        )
        for card in default_cards()
    ]

    return cards


def case_tools(
    case: SolutionCase,  # np. SolutionCase(card_changes={"90002": {…}}, …)
) -> list[AgentTool]:
    """
    Description:
    Narzędzia sprawy: atrapy wszystkich narzędzi, a gdy sprawa zmienia karty — odczyt kart na
    kartach sprawy. Wyszukiwania zostają wbudowane, więc znajdują te same numery.

    Example args:
        case=SolutionCase(card_changes={"90002": {"solution": "…"}}, …)

    Example result:
        [FakeFindTicketsVectorTool(), FakeFindTicketsTextTool(), FakeReadTicketsCardTool(cards=…),
         …]
    """
    if not case.card_changes:
        return fake_agent_tools()

    return fake_agent_tools_with_tickets(cards=case_cards(case), threads=None)


def cards_text(
    case: SolutionCase,  # np. SolutionCase(card_changes={"90002": {…}}, …)
) -> str:
    """
    Description:
    Cała treść kart, które model czyta w sprawie, w jednym tekście — do sprawdzenia, czy fakt
    stoi w materiale sprawy.

    Example args:
        case=SolutionCase(card_changes={"90002": {"solution": "…"}}, …)

    Example result:
        "90001 2026-02-10 e-Doręczenia Nie przychodzą przesyłki … Usunięto plik blokady; …"
    """
    return " ".join(str(value) for card in case_cards(case) for value in card.model_dump().values())


def ticket_subject(
    text: str,  # np. "ZGŁOSZENIE 90733 z 2026-10-13\nTemat: Po aktualizacji …\n…"
) -> str:
    """
    Description:
    Linia tematu zgłoszenia w kształcie `RawTicket.as_thread()`; po niej łączy się sprawy w pary.

    Example args:
        text="ZGŁOSZENIE 90733 z 2026-10-13\nTemat: Po aktualizacji nie przychodzą e-Doręczenia\n…"

    Example result:
        "Temat: Po aktualizacji nie przychodzą e-Doręczenia"
    """
    return next(line for line in text.split("\n") if line.startswith("Temat: "))


def mentions(
    text: str,   # np. "Takich wpisów nie da się usunąć."
    fact: Fact,  # np. ("nieodwracaln", "nie da się usunąć")
) -> bool:
    """
    Description:
    Mówi, czy fakt stoi w tekście: wystarczy jeden wariant, porównany zapisem `plain()`, czyli
    bez wielkich liter, polskich znaków i odstępów.

    Example args:
        text="Takich wpisów nie da się usunąć."
        fact=("nieodwracaln", "nie da się usunąć")

    Example result:
        True
    """
    flat = plain(text)

    return any(plain(variant) in flat for variant in fact)


def mentions_all(
    text:  str,               # np. "Przesyłkę odebrano ręcznie u operatora."
    facts: Sequence[Fact],    # np. (("ręczn",), ("operator",))
) -> bool:
    """
    Description:
    Mówi, czy w tekście stoją wszystkie fakty naraz — tak liczy się wzmianka z `should_mention`
    i `should_not_mention`.

    Example args:
        text="Przesyłkę odebrano ręcznie u operatora."
        facts=(("ręczn",), ("operator",))

    Example result:
        True
    """
    return all(mentions(text, fact) for fact in facts)


def question_marks(
    text: str,  # np. "1. Czy była aktualizacja? 2. Przy komunikacie „Zapisać?” wybrać Tak."
) -> int:
    """
    Description:
    Liczy znaki zapytania w tekście poza cytatem w polskim cudzysłowie i poza adresem: tam znak
    zapytania należy do komunikatu z ekranu albo do parametrów, a nie jest pytaniem do klienta.

    Example args:
        text="1. Czy była aktualizacja? 2. Przy komunikacie „Zapisać?” wybrać Tak."

    Example result:
        1
    """
    return NOT_A_QUESTION.sub("", text).count("?")


def judge_solution_case(
    case:    SolutionCase,     # np. SolutionCase(case_id="r03", must_mention=(…), …)
    output:  BaseModel | None,  # np. Proposal(…); None — `respond` nie przyjął odpowiedzi
    sources: Sequence[str],    # np. ("tickets:90002", "tickets:90003")
    retries: int,              # np. 0 — poprawki odpowiedzi od węzła `respond`
) -> SolutionOutcome:
    """
    Description:
    Ocenia jedną sprawę na samej treści dla klienta (`text`): które fakty z `must_mention` jej
    brakuje, czy stoją w niej wzmianki z `should_mention` i `should_not_mention` i ile jest w niej
    pytań do klienta. Wynik z samymi
    uwagami nie ma treści, więc nie niesie żadnego faktu. Brak wyniku zapisuje jako odpowiedź nie
    do przyjęcia, bez znalezisk.

    Example args:
        case=SolutionCase(case_id="r03", must_mention=(("ponowne pobr",), ("nieodwracaln",)), …)
        output=Proposal(text="… Ponowne pobranie tworzy wpisy, których nie da się usunąć. …", …)
        sources=("tickets:90002",)
        retries=0

    Example result:
        SolutionOutcome(case=…, rejected=False, text_given=True, missing=("nieodwracaln",),
                        expected_mention=None, forbidden_mention=None, questions=0,
                        sources=("tickets:90002",), retries=0, fields={…})
    """
    # --- brak wyniku: węzeł `respond` nie przyjął odpowiedzi mimo poprawki ---
    if output is None:
        rejected = SolutionOutcome(
            case              = case,
            rejected          = True,
            text_given        = False,
            missing           = (),
            expected_mention  = None,
            forbidden_mention = None,
            questions         = 0,
            sources           = (),
            retries           = retries,
            fields            = {},
        )

        return rejected

    fields   = output.model_dump(mode="json")
    text     = str(fields.get("text") or "")
    missing  = tuple(fact[0] for fact in case.must_mention if not mentions(text, fact))
    expected = mentions_all(text, case.should_mention) if case.should_mention else None
    unwanted = mentions_all(text, case.should_not_mention) if case.should_not_mention else None

    outcome = SolutionOutcome(
        case              = case,
        rejected          = False,
        text_given        = bool(text),
        missing           = missing,
        expected_mention  = expected,
        forbidden_mention = unwanted,
        questions         = question_marks(text),
        sources           = tuple(sources),
        retries           = retries,
        fields            = fields,
    )

    return outcome
