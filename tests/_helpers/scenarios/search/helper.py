"""
Description:
Zestaw scenariuszy rozpoznania (`data/safe/golden/search.json`) i ocena sprawy przeprowadzonej
na żywym modelu: czy graf `search` cytuje jako przyczynę plik, w którym stoi komunikat ze
zgłoszenia, czy nie cytuje przyczyny, gdy komunikatu nie ma w kodzie nigdzie, i czy cytuje
tylko linie, które wcześniej przeczytał. Narzędzia kodu są prawdziwe, na paczce aplikacji
syntetycznej, a zgłoszenia i instrukcje to atrapy. Korzysta z niego test ewaluacyjny
rozpoznania (p. 59). Modele zestawu i oceny leżą w `models/`, a raport, który pytest wypisuje
po przebiegu, w `report.py`.

| co                     | do czego                                                          |
|------------------------|-------------------------------------------------------------------|
| `search_sections()`    | sekcje zestawu po nazwie grafu                                    |
| `quoted_messages()`    | komunikaty z ekranu, które zgłoszenie cytuje w „…”                |
| `case_tools()`         | narzędzia sprawy: atrapy zgłoszeń i instrukcji, prawdziwy kod     |
| `code_quotes()`        | cytowania kodu z rozmowy, z tym, czy model je wcześniej przeczytał |
| `listing_count()`      | ile razy model wywołał spis katalogu kodu                         |
| `judge_search_case()`  | ocena jednej sprawy                                               |

Przykład — model zacytował fragment, którego wcześniej nie przeczytał:

    rozmowa: tura 1 find_code_text → linia 25 pliku RejestrSzablonow.php;
             tura 2 quote_code RejestrSzablonow.php:11-25, rola cause

    code_quotes(messages) -> [CodeQuote(fragment=CodeFragment("…/RejestrSzablonow.php", 11, 25),
                                        role="cause", read=False)]

Jak sprawa jest oceniana:

1. Przyczyną z kodu jest plik z cytowania w roli `cause`. Sprawa z `must_quote_as_cause`
   wymaga wśród nich swoich plików; sprawa z `must_not_quote_any_cause` nie dopuszcza żadnego;
   sprawa bez obu pól cytowań przyczyny nie sprawdza.
2. Linia jest odczytana, gdy oddał ją `read_code_file` albo `read_code_symbol` w jednej
   z wcześniejszych tur. Odczyt z tej samej tury co cytowanie się nie liczy: model wybrał
   zakres, zanim zobaczył linie. Linia widziana tylko w wyniku szukania odczytana nie jest.
3. Spis katalogu, nazwy w uwagach i fragment wykluczony przez wątek są tylko licznikami
   w raporcie: narzędzie spisu jest pomocnicze, a słowa uwag czyta się w całości.

O czym pamiętać przy zmianach:

- Cytowania i odczyty bierze się z rozmowy w stanie grafu, z wyników narzędzi, nie z argumentów:
  wywołanie, na które narzędzie oddało błąd, niczego nie odczytało ani nie zacytowało.
- Narzędzia kodu stoją na zbudowanej paczce syntetycznej; bez niej sprawa kończy się błędem
  z poleceniem budowy, zanim zawoła model.
"""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.agent_tools import AgentTool
from app.agent_tools.base import is_error_json
from app.engine_llm import ChatMessage
from tests._helpers.fake_tools import fake_agent_tools, fake_agent_tools_without_material
from tests._helpers.scenarios.search.constants import (
    CAUSE_ROLE,
    LIST_TOOL,
    META_KEY,
    QUOTE_TOOL,
    QUOTED_MESSAGE,
    READ_TOOLS,
    SEARCH_FILE,
)
from tests._helpers.scenarios.search.models.code_fragment import CodeFragment
from tests._helpers.scenarios.search.models.code_quote import CodeQuote
from tests._helpers.scenarios.search.models.search_case import SearchCase
from tests._helpers.scenarios.search.models.search_outcome import SearchOutcome
from tests._helpers.scenarios.search.models.search_section import SearchSection
from tests._helpers.synthetic_code import synthetic_code_tools


def search_sections(
    path: Path = SEARCH_FILE,  # np. Path("data/safe/golden/search.json")
) -> dict[str, SearchSection]:
    """
    Description:
    Czyta zestaw scenariuszy rozpoznania i oddaje jego sekcje po nazwie grafu, bez metryczki.

    Example args:
        path=Path("data/safe/golden/search.json")

    Example result:
        {"search": SearchSection(graph="search", cases=(SearchCase(case_id="k01", …), …))}
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    sections = {
        graph: SearchSection(
            graph = graph,
            cases = tuple(_case_from(entry) for entry in body["cases"]),
        )
        for graph, body in raw.items()
        if graph != META_KEY
    }

    return sections


def _case_from(
    entry: Mapping[str, Any],  # np. {"id": "k01", "must_quote_as_cause": ["src/…"], …}
) -> SearchCase:
    """
    Description:
    Zamienia wpis sprawy z zestawu na `SearchCase`. Pole, którego wpis nie ma, znaczy, że sprawa
    go nie sprawdza: pusta lista plików, `False` przy zakazie przyczyny albo brak fragmentu.

    Example args:
        entry={"id": "k01", "phenomenon": "…", "finds_tickets_and_docs": False,
               "must_quote_as_cause": ["src/lib/Urzad/Szablony/RejestrSzablonow.php"],
               "notes_should_include": ["wezwanie_stare"], "input": "ZGŁOSZENIE…"}

    Example result:
        SearchCase(case_id="k01", phenomenon="…", text="ZGŁOSZENIE…", finds_tickets_and_docs=False,
                   must_quote_as_cause=("src/lib/Urzad/Szablony/RejestrSzablonow.php",),
                   must_not_quote_any_cause=False, notes_should_include=("wezwanie_stare",),
                   should_not_quote_as_cause=None)
    """
    excluded = entry.get("should_not_quote_as_cause")

    case = SearchCase(
        case_id                   = entry["id"],
        phenomenon                = entry["phenomenon"],
        text                      = entry["input"],
        finds_tickets_and_docs    = entry["finds_tickets_and_docs"],
        must_quote_as_cause       = tuple(entry.get("must_quote_as_cause", ())),
        must_not_quote_any_cause  = entry.get("must_not_quote_any_cause", False),
        notes_should_include      = tuple(entry.get("notes_should_include", ())),
        should_not_quote_as_cause = None if excluded is None else CodeFragment(**excluded),
    )

    return case


def quoted_messages(
    text: str,  # np. "… pojawia się komunikat „W katalogu szablonów pism …”. …"
) -> tuple[str, ...]:
    """
    Description:
    Komunikaty z ekranu, które zgłoszenie cytuje w polskim cudzysłowie, w kolejności w tekście.

    Example args:
        text="Przy generowaniu pojawia się komunikat „W katalogu szablonów pism brakuje pliku”."

    Example result:
        ("W katalogu szablonów pism brakuje pliku",)
    """
    return tuple(QUOTED_MESSAGE.findall(text))


def case_tools(
    case: SearchCase,  # np. SearchCase(case_id="k01", finds_tickets_and_docs=False, …)
) -> list[AgentTool]:
    """
    Description:
    Narzędzia jednej sprawy: atrapy zgłoszeń i instrukcji — z wbudowanym materiałem albo puste,
    jak mówi sprawa — i sześć prawdziwych narzędzi kodu na paczce syntetycznej, w kolejności
    `TOOL_NAMES` grafów. Świeże na każde wywołanie, bo atrapy zapisują zapytania.

    Example args:
        case=SearchCase(case_id="k01", finds_tickets_and_docs=False, …)

    Example result:
        [FakeFindTicketsVectorTool(tickets=[]), …, DescribeCodeTool(…), FindCodeTextTool(…), …]

    Raises:
        AssertionError: paczki syntetycznej nie zbudowano
    """
    finds = case.finds_tickets_and_docs
    base  = fake_agent_tools() if finds else fake_agent_tools_without_material()
    code  = {tool.name: tool for tool in synthetic_code_tools()}

    tools = [code.get(tool.name, tool) for tool in base]

    return tools


def code_quotes(
    messages: Sequence[ChatMessage],  # np. state.messages — rozmowa z modelem
) -> list[CodeQuote]:
    """
    Description:
    Oddaje cytowania kodu z rozmowy, w kolejności wywołań, a przy każdym — czy wszystkie jego
    linie oddał wcześniej odczyt pliku albo symbolu. Odczyt z tej samej tury co cytowanie się nie
    liczy, a wywołania, na które narzędzie oddało błąd, są pomijane.

    Example args:
        messages=[ChatMessage(role="assistant", tool_calls=[ToolCall(name="read_code_file", …)]),
                  ChatMessage(role="tool", content='{"path": "src/a.php", "lines": […]}'), …]

    Example result:
        [CodeQuote(fragment=CodeFragment(path="src/a.php", from_line=3, to_line=7),
                   role="cause", read=True)]
    """
    results = {message.call_id: message.content for message in messages if message.role == "tool"}
    read: dict[str, set[int]] = {}
    quotes: list[CodeQuote] = []

    for turn in (message for message in messages if message.role == "assistant"):
        read_now: dict[str, set[int]] = {}

        for call in turn.tool_calls:
            content = results.get(call.call_id)

            # --- wywołanie bez wyniku (odpowiedź grafu) albo z błędem narzędzia ---
            if content is None or is_error_json(content):
                continue

            # --- odczyt pliku albo symbolu: linie z treścią, widoczne od następnej tury ---
            if call.name in READ_TOOLS:
                path, lines = _read_lines(json.loads(content))
                read_now.setdefault(path, set()).update(lines)
            # --- cytowanie: fragment i rola, sprawdzone wobec odczytów z wcześniejszych tur ---
            elif call.name == QUOTE_TOOL:
                quotes.append(_quote_from(json.loads(content), read))

        for path, lines in read_now.items():
            read.setdefault(path, set()).update(lines)

    return quotes


def _read_lines(
    body: Mapping[str, Any],  # np. {"path": "src/a.php", "lines": [{"line": 1, …}], …}
) -> tuple[str, set[int]]:
    """
    Description:
    Ścieżka i numery linii z wyniku odczytu: pliku (`path` na górze) albo symbolu (`symbol.path`).
    Odczyt symbolu, który oddał listę kandydatów zamiast definicji, nie odczytał żadnej linii.

    Example args:
        body={"symbol": {"path": "src/a.php", …}, "lines": [{"line": 4, "text": "…"}], …}

    Example result:
        ("src/a.php", {4})
    """
    symbol = body.get("symbol")
    path   = body.get("path") or (symbol or {}).get("path", "")
    lines  = {line["line"] for line in body.get("lines", [])}

    return path, lines


def _quote_from(
    body: Mapping[str, Any],    # np. {"path": "src/a.php", "from_line": 3, "to_line": 7, …}
    read: Mapping[str, set[int]],  # np. {"src/a.php": {1, 2, 3, 4, 5, 6, 7}}
) -> CodeQuote:
    """
    Description:
    Cytowanie z wyniku `quote_code`: fragment, rola i to, czy każda jego linia była już odczytana.

    Example args:
        body={"path": "src/a.php", "from_line": 3, "to_line": 7, "role": "cause"}
        read={"src/a.php": {1, 2, 3, 4, 5, 6, 7}}

    Example result:
        CodeQuote(fragment=CodeFragment(path="src/a.php", from_line=3, to_line=7),
                  role="cause", read=True)
    """
    fragment = CodeFragment(
        path      = body["path"],
        from_line = body["from_line"],
        to_line   = body["to_line"],
    )
    wanted = set(range(fragment.from_line, fragment.to_line + 1))

    quote = CodeQuote(
        fragment = fragment,
        role     = body["role"],
        read     = wanted <= read.get(fragment.path, set()),
    )

    return quote


def listing_count(
    messages: Sequence[ChatMessage],  # np. state.messages — rozmowa z modelem
) -> int:
    """
    Description:
    Liczy wywołania spisu katalogu kodu w rozmowie, także te, na które narzędzie oddało błąd:
    licznik mówi, czy model po spis sięgnął.

    Example args:
        messages=[ChatMessage(role="assistant", tool_calls=[ToolCall(name="list_code_files", …)])]

    Example result:
        1
    """
    count = sum(
        call.name == LIST_TOOL
        for message in messages
        if message.role == "assistant"
        for call in message.tool_calls
    )

    return count


def judge_search_case(
    case:     SearchCase,              # np. SearchCase(case_id="k01", …)
    output:   BaseModel | None,        # np. SearchNotes(…); None — `respond` nie przyjął odpowiedzi
    messages: Sequence[ChatMessage],   # np. state.messages; puste, gdy wyniku nie ma
    retries:  int,                     # np. 0 — poprawki odpowiedzi od węzła `respond`
) -> SearchOutcome:
    """
    Description:
    Ocenia jedną sprawę: pliki zacytowane jako przyczyna, cytowania linii nieodczytanych, spisy
    katalogu, nazwy brakujące w uwagach i fragment wykluczony przez wątek, zacytowany mimo to
    jako przyczyna. Brak wyniku zapisuje jako odpowiedź nie do przyjęcia, bez znalezisk.

    Example args:
        case=SearchCase(case_id="k01", must_quote_as_cause=("…/RejestrSzablonow.php",),
                        notes_should_include=("wezwanie_stare",), …)
        output=SearchNotes(internal_notes="## Kod aplikacji\\n- … wezwanie_stare.twig …")
        messages=state.messages
        retries=0

    Example result:
        SearchOutcome(case=…, rejected=False, cause_files=("…/RejestrSzablonow.php",), unread=(),
                      listings=1, missing_in_notes=(), ruled_out_cause_quoted=False, retries=0,
                      fields={…})
    """
    # --- brak wyniku: węzeł `respond` nie przyjął odpowiedzi mimo poprawki ---
    if output is None:
        rejected = SearchOutcome(
            case                   = case,
            rejected               = True,
            cause_files            = (),
            unread                 = (),
            listings               = 0,
            missing_in_notes       = (),
            ruled_out_cause_quoted = False,
            retries                = retries,
            fields                 = {},
        )

        return rejected

    fields = output.model_dump(mode="json")
    notes  = str(fields.get("internal_notes", "")).casefold()
    quotes = code_quotes(messages)
    causes = [quote.fragment for quote in quotes if quote.role == CAUSE_ROLE]
    excluded = case.should_not_quote_as_cause

    outcome = SearchOutcome(
        case                   = case,
        rejected               = False,
        cause_files            = tuple(dict.fromkeys(fragment.path for fragment in causes)),
        unread                 = tuple(quote.fragment.key for quote in quotes if not quote.read),
        listings               = listing_count(messages),
        missing_in_notes       = tuple(
            name for name in case.notes_should_include if name.casefold() not in notes
        ),
        ruled_out_cause_quoted = excluded is not None and any(
            fragment.overlaps(excluded) for fragment in causes
        ),
        retries                = retries,
        fields                 = fields,
    )

    return outcome
