"""
Description:
Próbki do testów samego helpera rozpoznania (`tests/unit/test_code_report.py`): trzy sprawy,
uwagi i klocki rozmowy — wywołania narzędzi kodu razem z wynikami w tym samym kształcie, w jakim
zapisuje je węzeł `run_tools`. Z klocków składa się rozmowę, na której test sprawdza, co ocena
liczy jako odczytane i zacytowane.

| co               | do czego                                                              |
|------------------|-----------------------------------------------------------------------|
| `CASE_IN_CODE`   | sprawa z wymaganym plikiem przyczyny i nazwą do wymienienia w uwagach |
| `CASE_NOWHERE`   | sprawa, która nie dopuszcza żadnej przyczyny                          |
| `CASE_THREAD`    | sprawa z wymaganym plikiem i fragmentem, którego nie powinien cytować |
| `NOTES`          | uwagi, które wymieniają nadmiarowy plik                               |
| `read_file()`    | odczyt pliku: wywołanie i wynik z liniami                             |
| `read_symbol()`  | odczyt symbolu: wywołanie i wynik z liniami definicji                 |
| `quote()`        | cytowanie fragmentu: wywołanie i potwierdzenie                        |
| `search_line()`  | szukanie: wywołanie i wynik z jedną linią                             |
| `failed()`       | wywołanie, na które narzędzie oddało błąd                             |
| `conversation()` | rozmowa z tur: każda tura to wywołania modelu i wyniki narzędzi       |

Przykład — odczyt w pierwszej turze, cytowanie w drugiej:

    messages = conversation(
        [read_file("c1", TEMPLATES, 1, 33)],
        [quote("c2", TEMPLATES, 11, 25, "cause")],
    )

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test helpera importuje je z tego modułu.
- Wyniki narzędzi powstają z ich modeli wyniku przez `result_as_json()`, jak w produkcie, więc
  zmiana kształtu wyniku narzędzia zmienia też próbki.
"""

from app.agent_tools.base import error_as_json, result_as_json
from app.agent_tools.code.find_code_text.models import FindCodeTextResult, MatchedLine
from app.agent_tools.code.quote_code.models import QuoteCodeResult
from app.agent_tools.code.read_code_file.models import (
    CodeFileInfo,
    ReadCodeFileResult,
    RequestedLines,
    ReturnedLines,
)
from app.agent_tools.code.read_code_symbol.models import (
    ReadCodeSymbolResult,
    RequestedSymbol,
    ReturnedSymbolLines,
    SymbolDefinition,
)
from app.core_util.text import number_lines
from app.engine_llm import ChatMessage, ToolCall
from tests._helpers.scenarios.code.models.code_case import CodeCase
from tests._helpers.scenarios.code.models.code_fragment import CodeFragment

# Plik z komunikatem o nadmiarowym szablonie: przyczyna w sprawie `CASE_IN_CODE`.
TEMPLATES = "src/lib/Urzad/Szablony/RejestrSzablonow.php"

# Plik pobierania skrzynki: w sprawie `CASE_THREAD` leży w nim przyczyna wykluczona przez klienta.
MAILBOX = "src/lib/Urzad/Wysylka/Edoreczenia/PobieranieSkrzynki.php"

# Początek zgłoszenia w kształcie `RawTicket.as_thread()`, wspólny dla spraw próbek.
TICKET_HEAD = "ZGŁOSZENIE 90001 z 2026-10-14\nTemat: Pisma\n\nOPIS ZGŁASZAJĄCEGO:\n"

# Sprawa, w której komunikat stoi tylko w kodzie: wymaga pliku przyczyny i nazwy pliku w uwagach.
CASE_IN_CODE = CodeCase(
    case_id                   = "k01",
    graphs                    = ("search",),
    phenomenon                = "komunikat tylko w kodzie",
    text                      = f"{TICKET_HEAD}„Jest nadmiarowy plik”",
    finds_tickets_and_docs    = False,
    must_quote_as_cause       = (TEMPLATES,),
    must_not_quote_any_cause  = False,
    notes_should_include      = ("wezwanie_stare",),
    should_not_quote_as_cause = None,
)

# Sprawa, w której komunikatu nie ma nigdzie: każde cytowanie przyczyny jest błędem.
CASE_NOWHERE = CodeCase(
    case_id                   = "k02",
    graphs                    = ("search",),
    phenomenon                = "komunikatu nie ma nigdzie",
    text                      = f"{TICKET_HEAD}„Brak szablonu nagłówka”",
    finds_tickets_and_docs    = False,
    must_quote_as_cause       = (),
    must_not_quote_any_cause  = True,
    notes_should_include      = (),
    should_not_quote_as_cause = None,
)

# Sprawa z wątkiem, w której klient wykluczył przyczynę z linii 35–37 pliku pobierania skrzynki.
CASE_THREAD = CodeCase(
    case_id                   = "k03",
    graphs                    = ("search",),
    phenomenon                = "wątek wyklucza załącznik",
    text                      = f"{TICKET_HEAD}Od wczoraj nie ma nowych przesyłek z e-Doręczeń.",
    finds_tickets_and_docs    = True,
    must_quote_as_cause       = (MAILBOX,),
    must_not_quote_any_cause  = False,
    notes_should_include      = (),
    should_not_quote_as_cause = CodeFragment(path=MAILBOX, from_line=35, to_line=37),
)

# Uwagi, które wymieniają nadmiarowy plik — nazwę ze sprawy `CASE_IN_CODE`.
NOTES = "## Kod aplikacji\n- RejestrSzablonow.php:11–25: plik Wezwanie_Stare.twig spoza listy typów"


def read_file(
    call_id:   str,  # np. "c1"
    path:      str,  # np. TEMPLATES
    from_line: int,  # np. 1
    to_line:   int,  # np. 33
) -> tuple[ToolCall, ChatMessage]:
    """
    Description:
    Odczyt pliku w rozmowie: wywołanie `read_code_file` i jego wynik z liniami od `from_line`
    do `to_line`, zapisany tak jak w produkcie.

    Example args:
        call_id="c1"
        path=TEMPLATES
        from_line=1
        to_line=33

    Example result:
        (ToolCall(call_id="c1", name="read_code_file", …),
         ChatMessage(role="tool", call_id="c1", content='{"path": "src/lib/…", …}'))
    """
    result = ReadCodeFileResult(
        path           = path,
        file_info      = CodeFileInfo(total_lines=to_line),
        requested      = RequestedLines(from_line=from_line, to_line=to_line),
        returned       = ReturnedLines(
            from_line    = from_line,
            to_line      = to_line,
            cut_by_limit = False,
            end_of_file  = True,
        ),
        numbered_lines = number_lines(["…"] * (to_line - from_line + 1), first=from_line),
    )
    call = ToolCall(call_id=call_id, name="read_code_file", arguments={"path": path})

    pair = (call, ChatMessage(role="tool", call_id=call_id, content=result_as_json(result)))

    return pair


def read_symbol(
    call_id:   str,  # np. "c1"
    path:      str,  # np. TEMPLATES
    from_line: int,  # np. 17
    to_line:   int,  # np. 32
) -> tuple[ToolCall, ChatMessage]:
    """
    Description:
    Odczyt symbolu w rozmowie: wywołanie `read_code_symbol` i jego wynik z jedną definicją
    i liniami od `from_line` do `to_line`.

    Example args:
        call_id="c1"
        path=TEMPLATES
        from_line=17
        to_line=32

    Example result:
        (ToolCall(call_id="c1", name="read_code_symbol", …),
         ChatMessage(role="tool", call_id="c1", content='{"symbol": {"path": "src/lib/…"}, …}'))
    """
    result = ReadCodeSymbolResult(
        requested      = RequestedSymbol(name="wczytaj", path=path),
        symbol         = SymbolDefinition(
            path      = path,
            name      = "wczytaj",
            scope     = "RejestrSzablonow",
            kind      = "method",
            from_line = from_line,
            to_line   = to_line,
        ),
        returned       = ReturnedSymbolLines(from_line=from_line, to_line=to_line,
                                             cut_by_limit=False),
        numbered_lines = number_lines(["…"] * (to_line - from_line + 1), first=from_line),
    )
    call = ToolCall(call_id=call_id, name="read_code_symbol", arguments={"name": "wczytaj"})

    pair = (call, ChatMessage(role="tool", call_id=call_id, content=result_as_json(result)))

    return pair


def quote(
    call_id:   str,  # np. "c2"
    path:      str,  # np. TEMPLATES
    from_line: int,  # np. 11
    to_line:   int,  # np. 25
    role:      str,  # np. "cause"; także "excluded"
) -> tuple[ToolCall, ChatMessage]:
    """
    Description:
    Cytowanie fragmentu w rozmowie: wywołanie `quote_code` i jego potwierdzenie.

    Example args:
        call_id="c2"
        path=TEMPLATES
        from_line=11
        to_line=25
        role="cause"

    Example result:
        (ToolCall(call_id="c2", name="quote_code", …),
         ChatMessage(role="tool", call_id="c2", content='{"path": "src/lib/…", "role": "cause"}'))
    """
    result = QuoteCodeResult(path=path, from_line=from_line, to_line=to_line, role=role)
    call   = ToolCall(
        call_id   = call_id,
        name      = "quote_code",
        arguments = {"path": path, "from_line": from_line, "to_line": to_line, "role": role},
    )

    pair = (call, ChatMessage(role="tool", call_id=call_id, content=result_as_json(result)))

    return pair


def search_line(
    call_id: str,  # np. "c1"
    path:    str,  # np. TEMPLATES
    line:    int,  # np. 25
) -> tuple[ToolCall, ChatMessage]:
    """
    Description:
    Szukanie w rozmowie: wywołanie `find_code_text` i wynik z jedną linią — jej treść model
    widzi, ale ocena nie liczy jej jako odczytanej.

    Example args:
        call_id="c1"
        path=TEMPLATES
        line=25

    Example result:
        (ToolCall(call_id="c1", name="find_code_text", …),
         ChatMessage(role="tool", call_id="c1", content='{"lines": [{"path": …, "line": 25}]}'))
    """
    result = FindCodeTextResult(
        lines = [
            MatchedLine(path=path, line=line, symbol="wczytaj", matched_by="exact", text="…"),
        ],
    )
    call = ToolCall(call_id=call_id, name="find_code_text", arguments={"exact": "nadmiarowy"})

    pair = (call, ChatMessage(role="tool", call_id=call_id, content=result_as_json(result)))

    return pair


def failed(
    call_id: str,  # np. "c3"
    name:    str,  # np. "list_code_files"
) -> tuple[ToolCall, ChatMessage]:
    """
    Description:
    Wywołanie narzędzia, na które narzędzie oddało błąd, zapisany tak jak w produkcie.

    Example args:
        call_id="c3"
        name="list_code_files"

    Example result:
        (ToolCall(call_id="c3", name="list_code_files", …),
         ChatMessage(role="tool", call_id="c3", content='{"error": "nie ma takiego katalogu"}'))
    """
    call  = ToolCall(call_id=call_id, name=name, arguments={"path": "src/nie-ma"})
    error = error_as_json("nie ma takiego katalogu")

    pair = (call, ChatMessage(role="tool", call_id=call_id, content=error))

    return pair


def conversation(
    *turns: list[tuple[ToolCall, ChatMessage]],  # np. [read_file(…)], [quote(…)]
) -> list[ChatMessage]:
    """
    Description:
    Składa rozmowę z tur: każda tura to wiadomość modelu z jej wywołaniami, a po niej wyniki
    narzędzi w tej samej kolejności — tak jak zapisuje je pętla agenta.

    Example args:
        turns=([read_file("c1", TEMPLATES, 1, 33)], [quote("c2", TEMPLATES, 11, 25, "cause")])

    Example result:
        [ChatMessage(role="assistant", tool_calls=[ToolCall(call_id="c1", …)]),
         ChatMessage(role="tool", call_id="c1", …),
         ChatMessage(role="assistant", tool_calls=[ToolCall(call_id="c2", …)]),
         ChatMessage(role="tool", call_id="c2", …)]
    """
    messages: list[ChatMessage] = []

    for turn in turns:
        messages.append(ChatMessage(role="assistant", tool_calls=[call for call, _ in turn]))
        messages.extend(result for _, result in turn)

    return messages
