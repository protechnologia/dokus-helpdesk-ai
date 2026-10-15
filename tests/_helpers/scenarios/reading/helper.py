"""
Description:
Zestaw scenariuszy czytania znalezionego materiału (`data/safe/golden/reading.json`) i ocena
sprawy przeprowadzonej na żywym modelu: czy graf z narzędziami wiedzy przeczytał to, co znalazł —
wszystkie karty zgłoszeń o jednym objawie i trzech przyczynach, właściwą sekcję instrukcji obok
dystraktora — czy wynik nazywa przyczyny z przeczytanych kart i te, które odpowiedzi klienta
wykluczają, i ile razy sięgnął po kod aplikacji. Narzędzia to atrapy, a ich wyszukiwania oddają
zawsze ten sam wynik. Korzysta z niego test ewaluacyjny czytania (p. 59). Modele zestawu i oceny
leżą w `models/`, a raport, który pytest wypisuje po przebiegu, w `report.py`.

| co                     | do czego                                                       |
|------------------------|----------------------------------------------------------------|
| `reading_cases()`      | wszystkie sprawy zestawu, każda raz                            |
| `reading_sections()`   | sprawy w sekcjach po nazwie grafu, z pola `graphs` sprawy      |
| `case_keys()`          | wszystkie klucze źródeł, które sprawa wymienia                 |
| `found_material()`     | klucze źródeł, które atrapy znajdują i umieją odczytać         |
| `material_units()`     | treść materiału atrap po kluczu źródła                         |
| `material_text()`      | cała treść materiału atrap w jednym tekście                    |
| `code_calls()`         | ile razy model wywołał narzędzia kodu                          |
| `excluded_in_notes()`  | które fakty uwagi nazywają w linii ze słowem wykluczenia       |
| `judge_reading_case()` | ocena jednej sprawy                                            |

Przykład — model przeczytał dwie karty z trzech i w uwagach wykluczył załącznik:

    outcome = judge_reading_case(
        case     = ReadingCase(case_id="c02", must_read=("tickets:90001", "tickets:90002",
                               "tickets:90003"), should_exclude=(("90003", "limit operatora"),), …),
        output   = SearchNotes(internal_notes="…\\nOdpowiedź klienta wyklucza załącznik ponad
                               limit operatora (90003).\\n…"),
        sources  = ("tickets:90001", "tickets:90002"),
        messages = state.messages,
        retries  = 0,
    )

    outcome.unread     -> ("tickets:90003",)
    outcome.excluded   -> ("90003",)
    outcome.assessment -> "NIEPRZECZYTANE: tickets:90003"

Jak sprawa jest oceniana:

1. Warunek: każdy klucz z `must_read` stoi na liście źródeł, czyli model ten materiał odczytał.
   Znaleziony, ale nieprzeczytany źródłem nie jest.
2. Liczniki: klucze z `should_read` i `should_not_read` na liście źródeł; fakty z `should_name`
   w którymkolwiek polu tekstowym wyniku; fakty z `should_exclude` w linii uwag razem ze słowem
   wykluczenia; wywołania narzędzi kodu w rozmowie, a w sprawie z `should_not_call_code` każde
   z nich jest niepożądane.

O czym pamiętać przy zmianach:

- Fakty porównuje się zapisem `plain()` helpera „Popraw”, tak jak w scenariuszach rozwiązania:
  bez wielkich liter, polskich znaków i odstępów.
- Licznik wykluczenia liczy słowa, nie sens: linia „wykluczono kolejkę, zostaje załącznik” też
  liczy się jako wykluczenie załącznika, a „nie jest definitywnie wykluczone” — jako
  wykluczenie, bo zaprzeczenie nie stoi tuż przed słowem. Uwagi czyta się w raporcie.
- Wywołania narzędzi kodu liczy się wszystkie, także te, na które narzędzie oddało błąd: licznik
  mówi, czy model po kod sięgnął.
"""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.agent_tools.docs.fake_docs import default_sections, default_texts
from app.agent_tools.tickets.fake_tickets import default_cards, default_threads
from app.agent_tools.tickets.find_tickets_text.fake import default_matched
from app.agent_tools.tickets.find_tickets_vector.fake import default_found
from app.engine_llm import ChatMessage
from tests._helpers.scenarios.polish import plain
from tests._helpers.scenarios.reading.constants import (
    CASES_KEY,
    CODE_TOOLS,
    EXCLUSION_WORDS,
    NEGATED_EXCLUSION,
    READING_FILE,
)
from tests._helpers.scenarios.reading.models.reading_case import ReadingCase
from tests._helpers.scenarios.reading.models.reading_outcome import ReadingOutcome
from tests._helpers.scenarios.reading.models.reading_section import ReadingSection
from tests._helpers.scenarios.solution import Fact, mentions


def reading_cases(
    path: Path = READING_FILE,  # np. Path("data/safe/golden/reading.json")
) -> tuple[ReadingCase, ...]:
    """
    Description:
    Czyta wszystkie sprawy zestawu scenariuszy czytania, w kolejności zestawu, każdą raz, bez
    względu na to, na ilu grafach idzie.

    Example args:
        path=Path("data/safe/golden/reading.json")

    Example result:
        (ReadingCase(case_id="c01", graphs=("search", "suggest_questions", …), …), …)
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    return tuple(_case_from(entry) for entry in raw[CASES_KEY])


def reading_sections(
    path: Path = READING_FILE,  # np. Path("data/safe/golden/reading.json")
) -> dict[str, ReadingSection]:
    """
    Description:
    Składa sprawy zestawu w sekcje po nazwie grafu: sekcja grafu ma każdą sprawę, która go
    wymienia w `graphs`, w kolejności zestawu. Grafy stoją w kolejności pierwszego wystąpienia.

    Example args:
        path=Path("data/safe/golden/reading.json")

    Example result:
        {"search": ReadingSection(graph="search", cases=(ReadingCase(case_id="c01", …), …)),
         "suggest_questions": ReadingSection(graph="suggest_questions", cases=(…)), …}
    """
    by_graph: dict[str, list[ReadingCase]] = {}

    for case in reading_cases(path):
        for graph in case.graphs:
            by_graph.setdefault(graph, []).append(case)

    sections = {
        graph: ReadingSection(graph=graph, cases=tuple(cases))
        for graph, cases in by_graph.items()
    }

    return sections


def _case_from(
    entry: Mapping[str, Any],  # np. {"id": "c01", "graphs": ["search"], "must_read": […], …}
) -> ReadingCase:
    """
    Description:
    Zamienia wpis sprawy z zestawu na `ReadingCase`. Pole, którego wpis nie ma, znaczy, że sprawa
    go nie sprawdza: pusta lista kluczy albo faktów, a przy kodzie — `False`.

    Example args:
        entry={"id": "c03", "graphs": ["search"], "phenomenon": "…",
               "should_read": ["docs:adm-kancelaria-edoreczenia"],
               "should_name": [["zalog", "przelog"]], "input": "ZGŁOSZENIE…"}

    Example result:
        ReadingCase(case_id="c03", graphs=("search",), phenomenon="…", text="ZGŁOSZENIE…",
                    must_read=(), should_read=("docs:adm-kancelaria-edoreczenia",),
                    should_not_read=(), should_name=(("zalog", "przelog"),), should_exclude=(),
                    should_not_call_code=False)
    """
    case = ReadingCase(
        case_id              = entry["id"],
        graphs               = tuple(entry["graphs"]),
        phenomenon           = entry["phenomenon"],
        text                 = entry["input"],
        must_read            = tuple(entry.get("must_read", ())),
        should_read          = tuple(entry.get("should_read", ())),
        should_not_read      = tuple(entry.get("should_not_read", ())),
        should_name          = _facts(entry.get("should_name", ())),
        should_exclude       = _facts(entry.get("should_exclude", ())),
        should_not_call_code = entry.get("should_not_call_code", False),
    )

    return case


def _facts(
    raw: Sequence[Sequence[str]],  # np. [["kolejk"], ["załącznik", "limit"]]
) -> tuple[Fact, ...]:
    """
    Description:
    Zamienia listę faktów z zestawu (każdy to lista wariantów) na krotki.

    Example args:
        raw=[["kolejk"], ["załącznik", "limit"]]

    Example result:
        (("kolejk",), ("załącznik", "limit"))
    """
    return tuple(tuple(variants) for variants in raw)


def case_keys(
    case: ReadingCase,  # np. ReadingCase(must_read=("tickets:90001",), …)
) -> tuple[str, ...]:
    """
    Description:
    Wszystkie klucze źródeł, które sprawa wymienia: wymagane, oczekiwane i niepożądane,
    w tej kolejności.

    Example args:
        case=ReadingCase(must_read=("tickets:90001",), should_read=("docs:a",), …)

    Example result:
        ("tickets:90001", "docs:a")
    """
    return (*case.must_read, *case.should_read, *case.should_not_read)


def found_material() -> frozenset[str]:
    """
    Description:
    Klucze źródeł materiału, który atrapy znajdują i umieją odczytać: zgłoszenia z wbudowanych
    wyników obu wyszukiwań zgłoszeń, które mają kartę albo wątek, i każda sekcja dokumentacji,
    bo spis treści atrapy wymienia wszystkie.

    Example args:
        (brak)

    Example result:
        frozenset({"tickets:90001", "tickets:90002", "tickets:90003", "tickets:90011",
                   "tickets:90012", "docs:adm-kancelaria-edoreczenia", …})
    """
    readable = {card.ticket_id for card in default_cards()}
    readable |= {thread.ticket_id for thread in default_threads()}
    found    = [ticket.ticket_id for ticket in [*default_found(), *default_matched()]]

    keys = frozenset(
        [f"tickets:{number}" for number in found if number in readable]
        + [f"docs:{section.section_id}" for section in default_sections()]
    )

    return keys


def material_units() -> dict[str, str]:
    """
    Description:
    Treść materiału atrap po kluczu źródła: zgłoszenie to pola jego karty razem z wątkiem,
    sekcja dokumentacji to tytuł z treścią. Po niej test zestawu sprawdza, w ilu sprawach albo
    sekcjach stoi fakt.

    Example args:
        (brak)

    Example result:
        {"tickets:90001": "90001 2026-02-10 e-Doręczenia … ZGŁOSZENIE 90001 z 2026-02-10 …",
         "docs:adm-kancelaria-edoreczenia": "Uprawnienie do kancelarii e-Doręczeń …", …}
    """
    parts: dict[str, list[str]] = {}

    for card in default_cards():
        parts.setdefault(f"tickets:{card.ticket_id}", []).extend(
            str(value) for value in card.model_dump().values()
        )

    for thread in default_threads():
        parts.setdefault(f"tickets:{thread.ticket_id}", []).append(thread.thread)

    texts = default_texts()

    for section in default_sections():
        parts[f"docs:{section.section_id}"] = [section.title, texts[section.section_id]]

    units = {key: " ".join(texts_of_key) for key, texts_of_key in parts.items()}

    return units


def material_text() -> str:
    """
    Description:
    Cała treść materiału atrap w jednym tekście: karty i wątki zgłoszeń oraz sekcje
    dokumentacji. Po nim test zestawu sprawdza, że fakt, który wynik ma nazwać, model może wziąć
    z odczytu.

    Example args:
        (brak)

    Example result:
        "90001 2026-02-10 e-Doręczenia … Uprawnienie do kancelarii e-Doręczeń nadaje …"
    """
    return " ".join(material_units().values())


def code_calls(
    messages: Sequence[ChatMessage],  # np. state.messages — rozmowa z modelem
) -> int:
    """
    Description:
    Liczy wywołania narzędzi kodu w rozmowie, także te, na które narzędzie oddało błąd: licznik
    mówi, czy model po kod sięgnął.

    Example args:
        messages=[ChatMessage(role="assistant", tool_calls=[ToolCall(name="find_code_text", …),
                                                             ToolCall(name="read_docs", …)])]

    Example result:
        1
    """
    count = sum(
        call.name in CODE_TOOLS
        for message in messages
        if message.role == "assistant"
        for call in message.tool_calls
    )

    return count


def excluded_in_notes(
    notes: str,               # np. "…\nOdpowiedź klienta wyklucza załącznik ponad limit.\n…"
    facts: Sequence[Fact],    # np. (("załącznik", "limit"),)
) -> tuple[str, ...]:
    """
    Description:
    Oddaje fakty (pierwszym wariantem), które uwagi nazywają jako wykluczone: w jednej linii
    stoi fakt i któreś ze słów wykluczenia, bez zaprzeczenia tuż przed nim. Fakt w innej linii
    niż słowo się nie liczy, a „nie wyklucza” i „niewykluczone” nie są wykluczeniem.

    Example args:
        notes="- 90003: załącznik ponad limit operatora\nOdpowiedź klienta wyklucza 90003."
        facts=(("90003", "limit operatora"),)

    Example result:
        ("90003",)
    """
    lines = [line for line in notes.split("\n") if _excludes(line)]

    excluded = tuple(fact[0] for fact in facts if any(mentions(line, fact) for line in lines))

    return excluded


def _excludes(
    line: str,  # np. "Odpowiedź klienta wyklucza 90003; kolejka pozostaje niewykluczona."
) -> bool:
    """
    Description:
    Mówi, czy linia niesie słowo wykluczenia po wycięciu słów wykluczenia z zaprzeczeniem tuż
    przed nimi.

    Example args:
        line="Odpowiedź klienta wyklucza 90003; kolejka pozostaje niewykluczona."

    Example result:
        True — „wyklucza” zostaje po wycięciu „niewykluczona”
    """
    bare = plain(NEGATED_EXCLUSION.sub("", line.casefold()))

    return any(plain(word) in bare for word in EXCLUSION_WORDS)


def judge_reading_case(
    case:     ReadingCase,            # np. ReadingCase(case_id="c01", must_read=(…), …)
    output:   BaseModel | None,       # np. SearchNotes(…); None — `respond` nie przyjął odpowiedzi
    sources:  Sequence[str],          # np. ("tickets:90001", "tickets:90002")
    messages: Sequence[ChatMessage],  # np. state.messages; puste, gdy wyniku nie ma
    retries:  int,                    # np. 0 — poprawki odpowiedzi od węzła `respond`
) -> ReadingOutcome:
    """
    Description:
    Ocenia jedną sprawę: klucze z `must_read` spoza listy źródeł, klucze oczekiwane
    i niepożądane na liście, fakty nazwane w wyniku, fakty nazwane w uwagach jako wykluczone
    i wywołania narzędzi kodu. Brak wyniku zapisuje jako odpowiedź nie do przyjęcia, bez
    znalezisk.

    Example args:
        case=ReadingCase(case_id="c01", must_read=("tickets:90001", …),
                         should_name=(("kolejk",), …), …)
        output=SearchNotes(internal_notes="## Zgłoszenia historyczne\\n- 90001: zacięta kolejka…")
        sources=("tickets:90001", "tickets:90002", "tickets:90003")
        messages=state.messages
        retries=0

    Example result:
        ReadingOutcome(case=…, rejected=False, sources=(…), unread=(), read_wanted=(),
                       read_unwanted=(), named=("kolejk", "blokad", "załącznik"), excluded=(),
                       code_calls=3, retries=0, fields={…})
    """
    # --- brak wyniku: węzeł `respond` nie przyjął odpowiedzi mimo poprawki ---
    if output is None:
        rejected = ReadingOutcome(
            case          = case,
            rejected      = True,
            sources       = (),
            unread        = (),
            read_wanted   = (),
            read_unwanted = (),
            named         = (),
            excluded      = (),
            code_calls    = 0,
            retries       = retries,
            fields        = {},
        )

        return rejected

    fields = output.model_dump(mode="json")
    text   = " ".join(value for value in fields.values() if isinstance(value, str))
    notes  = str(fields.get("internal_notes") or "")

    outcome = ReadingOutcome(
        case          = case,
        rejected      = False,
        sources       = tuple(sources),
        unread        = tuple(key for key in case.must_read if key not in sources),
        read_wanted   = tuple(key for key in case.should_read if key in sources),
        read_unwanted = tuple(key for key in case.should_not_read if key in sources),
        named         = tuple(fact[0] for fact in case.should_name if mentions(text, fact)),
        excluded      = excluded_in_notes(notes, case.should_exclude),
        code_calls    = code_calls(messages),
        retries       = retries,
        fields        = fields,
    )

    return outcome
