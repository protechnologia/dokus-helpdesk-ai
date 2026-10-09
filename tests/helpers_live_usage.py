"""
Description:
Raport zużycia żywego, płatnego modelu w testach `llm_live`: zbiera zużycie każdej sprawy
i składa podsumowanie, które pytest wypisuje na końcu przebiegu — linię na sprawę, pod nią
przebieg grafu z wywołaniami narzędzi, a na końcu sumę kosztu.

| co                    | do czego                                                          |
|-----------------------|-------------------------------------------------------------------|
| `LiveUsageReport`     | raport: `record()` dopisuje sprawę, `lines()` składa podsumowanie |
| `LiveUsage`           | jedna zgłoszona sprawa: etykieta, zużycie, przebieg i rozmowa     |
| `usage_as_text()`     | zużycie jedną linią dla człowieka                                 |
| `run_as_lines()`      | wpisy przebiegu, a pod każdą turą modelu jej wywołania narzędzi   |
| `arguments_as_text()` | argumenty wywołania jedną linią                                   |
| `result_as_summary()` | wynik narzędzia w skrócie: liczby i flagi zamiast treści          |

Przykład — dwie sprawy i to, co pytest wypisze po przebiegu:

    report.record("graf search", state.usage, state.log, state.messages)
    report.record("complete: zwykłe pytanie", usage)

    graf search: wywołań 5, świeże wejście 412, zapis do cache 8120, odczyt z cache 25010, …
        agent: tura 1: narzędzia: find_code_text; 0,0041 USD
            find_code_text {"exact": "Brak sekwencji numeracji"}
                → lines: 2, omitted_over_limit: 0
        run_tools: wywołania: find_code_text; źródła: 0
        agent: tura 2: narzędzia: read_code_file; 0,0038 USD
            read_code_file {"path": "src/lib/Urzad/Numeracja/GeneratorNumeru.php", "to_line": 30}
                → path: src/lib/Urzad/Numeracja/GeneratorNumeru.php, file_info.total_lines: 14, …
        run_tools: wywołania: read_code_file; źródła: 0
    complete: zwykłe pytanie: wywołań 1, świeże wejście 30, zapis do cache 0, …
    RAZEM: wywołań 6, …, koszt 0,0272 USD

Jak czytać opis wyniku narzędzia (linia ze strzałką):

| co stoi w wyniku     | co widać w opisie                        |
|----------------------|------------------------------------------|
| lista                | nazwa pola i liczba pozycji (`lines: 2`) |
| liczba, flaga, `null`| nazwa pola i wartość                     |
| pole w grupie        | pełna ścieżka (`returned.to_line: 14`)   |
| krótki tekst         | nazwa pola i tekst                       |
| długi tekst          | nazwa pola i długość (`thread: 1840 zn.`)|
| błąd narzędzia       | `błąd:` i komunikat, który dostał model  |

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `live_usage` z `tests/conftest.py`, jeden na cały przebieg.
  Tam też stoi funkcja, która go wypisuje: pytest szuka fixture'ów i swoich haków tylko
  w `conftest.py`. Obiekt zbudowany w teście nie trafiłby do podsumowania.
- Sumę liczy się z pola `usage` każdej sprawy. Wpisy `log` są tylko wypisywane: to tekst dla
  człowieka, z którego liczb się nie wyciąga.
- Wywołania narzędzi bierze się z rozmowy (`messages` stanu grafu), nie z `log`: wpis przebiegu
  niesie same nazwy i liczby, bo wraca w odpowiedzi każdej trasy, a argumenty wyszukiwań to
  treść zgłoszenia. Dlatego ten wydruk jest dla testów na zmyślonych zgłoszeniach.
- Tura modelu i wpis węzła `agent` idą parami, w tej samej kolejności: każde wywołanie węzła
  dokłada jedną turę do rozmowy i jeden wpis do przebiegu. Na tym stoi `run_as_lines()`.
- Sprawa zakończona błędem nie oddaje stanu, więc jej zużycia w raporcie nie ma.
"""

import dataclasses
import functools
import json
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from app.agent_nodes.models import LogEntry
from app.agent_tools.base import is_error_json
from app.engine_llm import ChatMessage, LLMUsage

# Dłuższe argumenty wywołania są ucinane: narzędzie odpowiedzi niesie w nich całą propozycję.
MAX_ARGUMENTS_CHARS = 300

# Tekst w wyniku narzędzia dłuższy niż tyle znaków jest w opisie zastąpiony swoją długością.
MAX_RESULT_TEXT_CHARS = 80

# Tym znakiem kończą się ucięte argumenty.
CUT_MARK = "…"


@dataclasses.dataclass(frozen=True)
class LiveUsage:
    """Zużycie jednej sprawy na żywym modelu, zgłoszone przez test."""

    label:    str                      # np. "graf search"
    usage:    LLMUsage                 # wywołania, tokeny i koszt całej sprawy
    log:      tuple[LogEntry, ...]     # wpisy przebiegu grafu; puste poza sprawami grafów
    messages: tuple[ChatMessage, ...]  # rozmowa z modelem; pusta, gdy test jej nie zgłosił


class LiveUsageReport:
    """
    Description:
    Zbiera zużycie spraw przeprowadzonych na żywym, płatnym modelu w jednym przebiegu pytesta
    i składa z niego podsumowanie: linię na sprawę, pod nią przebieg grafu z wywołaniami
    narzędzi, a na końcu sumę.

    Do czego:
    Testy `llm_live` sprawdzają okablowanie, ale każdy ich przebieg kosztuje. Bez tego
    podsumowania koszt trzeba było liczyć osobno, a tego, których narzędzi model użył i o co je
    pytał, nie było widać wcale.

    Flow:
        1. Test dostaje raport przez fixture `live_usage` i woła `record()` raz na sprawę —
           tam, gdzie liczy odpowiedź modelu.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.

    Sumę liczy się z pola `usage` każdej sprawy. Wpisy `log` i wywołania narzędzi są tylko
    wypisywane: to tekst dla człowieka, z którego liczb się nie wyciąga.
    """

    def __init__(self) -> None:
        """
        Description:
        Zakłada pusty raport.

        Example args:
            (brak)

        Example result:
            LiveUsageReport bez zgłoszonych spraw
        """
        self._records: list[LiveUsage] = []

    def record(
        self,
        label:    str,                        # np. "graf search"
        usage:    LLMUsage,                   # np. state.usage — zużycie całej sprawy
        log:      Sequence[LogEntry] = (),    # np. state.log — wpisy przebiegu grafu
        messages: Sequence[ChatMessage] = (), # np. state.messages — rozmowa z modelem
    ) -> None:
        """
        Description:
        Dopisuje do raportu jedną sprawę: jej zużycie i, jeśli szła przez graf, wpisy przebiegu
        oraz rozmowę, z której raport wypisze wywołania narzędzi.

        Example args:
            label="graf search"
            usage=LLMUsage(calls=5, prompt_tokens=412, cost_usd=0.027)
            log=[LogEntry(node="agent", message="tura 1: narzędzia: read_docs; 0,0041 USD")]
            messages=[ChatMessage(role="assistant", tool_calls=[ToolCall(name="read_docs", …)])]

        Example result:
            None — sprawa jest w raporcie
        """
        record = LiveUsage(
            label    = label,
            usage    = usage,
            log      = tuple(log),
            messages = tuple(messages),
        )

        self._records.append(record)

    def lines(self) -> list[str]:
        """
        Description:
        Składa podsumowanie: dla każdej sprawy linię z wywołaniami, tokenami w czterech klasach
        i kosztem, pod nią wcięty przebieg grafu z wywołaniami narzędzi, a na końcu linię
        „RAZEM" z sumą. Pusty raport daje pustą listę.

        Example args:
            (brak)

        Example result:
            ["graf search: wywołań 5, świeże wejście 412, zapis do cache 8120, odczyt z cache "
             "25010, wyjście 640, koszt 0,0270 USD",
             "    agent: tura 1: narzędzia: read_docs; 0,0041 USD",
             '        read_docs {"section_ids": ["usr-odswiezanie"]}',
             "            → sections: 1",
             "RAZEM: wywołań 5, świeże wejście 412, zapis do cache 8120, odczyt z cache 25010, "
             "wyjście 640, koszt 0,0270 USD"]
        """
        # --- nic nie zgłoszono: przebieg bez testów na żywym modelu ---
        if not self._records:
            return []

        lines: list[str] = []

        for record in self._records:
            lines.append(f"{record.label}: {usage_as_text(record.usage)}")
            lines.extend(run_as_lines(record.log, record.messages))

        total = functools.reduce(LLMUsage.plus, (record.usage for record in self._records))
        lines.append(f"RAZEM: {usage_as_text(total)}")

        return lines


def usage_as_text(
    usage: LLMUsage,  # np. LLMUsage(calls=5, prompt_tokens=412, cost_usd=0.027)
) -> str:
    """
    Description:
    Zapisuje zużycie jedną linią dla człowieka: wywołania, cztery klasy tokenów i koszt
    z przecinkiem dziesiętnym, jak we wpisach przebiegu grafu.

    Example args:
        usage=LLMUsage(calls=5, prompt_tokens=412, cache_write_tokens=8120,
                       cache_read_tokens=25010, completion_tokens=640, cost_usd=0.027)

    Example result:
        "wywołań 5, świeże wejście 412, zapis do cache 8120, odczyt z cache 25010, wyjście 640, "
        "koszt 0,0270 USD"
    """
    cost = f"{usage.cost_usd:.4f}".replace(".", ",")

    text = (
        f"wywołań {usage.calls}, świeże wejście {usage.prompt_tokens}, "
        f"zapis do cache {usage.cache_write_tokens}, odczyt z cache {usage.cache_read_tokens}, "
        f"wyjście {usage.completion_tokens}, koszt {cost} USD"
    )

    return text


def run_as_lines(
    log:      Sequence[LogEntry],     # np. state.log — wpisy przebiegu grafu
    messages: Sequence[ChatMessage],  # np. state.messages — rozmowa z modelem; może być pusta
) -> list[str]:
    """
    Description:
    Zamienia przebieg jednej sprawy na wcięte linie raportu: każdy wpis przebiegu w swojej
    linii, a pod wpisem tury modelu (`agent`) wywołania narzędzi z tej tury — nazwa
    z argumentami i, linię niżej, opis wyniku, który model dostał. Bez rozmowy oddaje same
    wpisy przebiegu.

    Turę modelu do wpisu dobiera kolejność: N-ty wpis węzła `agent` to N-ta tura modelu
    w rozmowie. Wynik do wywołania dobiera identyfikator wywołania (`call_id`). Wywołanie bez
    wyniku — narzędzie odpowiedzi przyjęte przez węzeł `respond` — ma samą linię z argumentami.

    Example args:
        log=[LogEntry(node="agent", message="tura 1: narzędzia: find_code_text; 0,0041 USD"),
             LogEntry(node="run_tools", message="wywołania: find_code_text; źródła: 0")]
        messages=[ChatMessage(role="assistant", tool_calls=[
                      ToolCall(call_id="call_1", name="find_code_text",
                               arguments={"exact": "Brak sekwencji numeracji"})]),
                  ChatMessage(role="tool", call_id="call_1",
                              content='{"lines": […], "omitted_over_limit": 0}')]

    Example result:
        ["    agent: tura 1: narzędzia: find_code_text; 0,0041 USD",
         '        find_code_text {"exact": "Brak sekwencji numeracji"}',
         "            → lines: 2, omitted_over_limit: 0",
         "    run_tools: wywołania: find_code_text; źródła: 0"]
    """
    turns   = iter(message for message in messages if message.role == "assistant")
    results = {message.call_id: message.content for message in messages if message.role == "tool"}

    lines: list[str] = []

    for entry in log:
        lines.append(f"    {entry.node}: {entry.message}")

        # --- tylko tura modelu niesie wywołania narzędzi ---
        if entry.node != "agent":
            continue

        turn = next(turns, None)

        # --- sprawa zgłoszona bez rozmowy albo z rozmową krótszą niż przebieg ---
        if turn is None:
            continue

        for call in turn.tool_calls:
            lines.append(f"        {call.name} {arguments_as_text(call.arguments)}")

            if call.call_id in results:
                lines.append(f"            → {result_as_summary(results[call.call_id])}")

    return lines


def arguments_as_text(
    arguments: Mapping[str, Any],  # np. {"path": "src/web/js/_global/bledy.js", "to_line": 30}
) -> str:
    """
    Description:
    Zapisuje argumenty wywołania narzędzia jedną linią, jako JSON z polskimi literami. Zapis
    dłuższy niż `MAX_ARGUMENTS_CHARS` jest ucinany i kończy się znakiem „…".

    Example args:
        arguments={"path": "src/web/js/_global/bledy.js", "to_line": 30}

    Example result:
        '{"path": "src/web/js/_global/bledy.js", "to_line": 30}'
    """
    text = json.dumps(arguments, ensure_ascii=False)

    if len(text) <= MAX_ARGUMENTS_CHARS:
        return text

    return text[:MAX_ARGUMENTS_CHARS] + CUT_MARK


def result_as_summary(
    content: str,  # np. '{"lines": [{"path": "…", "line": 9, …}], "omitted_over_limit": 0}'
) -> str:
    """
    Description:
    Opisuje wynik narzędzia jedną linią, bez treści: z JSON-a, który dostał model, zostają nazwy
    pól z liczbami, flagami i krótkimi tekstami, lista jest zastąpiona liczbą pozycji, a długi
    tekst swoją długością. Pole w grupie stoi pod pełną ścieżką. Błąd narzędzia wraca jako
    „błąd:" z komunikatem.

    Example args:
        content='{"path": "src/a.php", "file_info": {"total_lines": 14},
                  "returned": {"from_line": 1, "to_line": 14, "end_of_file": true},
                  "lines": [{"line": 1, "text": "<?php"}, …]}'

    Example result:
        "path: src/a.php, file_info.total_lines: 14, returned.from_line: 1, "
        "returned.to_line: 14, returned.end_of_file: true, lines: 14"
    """
    # --- błąd narzędzia: komunikat w całości, bo po nim widać, co model zrobił źle ---
    if is_error_json(content):
        return f"błąd: {json.loads(content)['error']}"

    try:
        body = json.loads(content)
    except json.JSONDecodeError:  # wynik, który nie jest JSON-em
        return f"tekst, {len(content)} zn."

    # --- JSON, który nie jest obiektem: nie ma pól do wypisania ---
    if not isinstance(body, dict):
        return f"tekst, {len(content)} zn."

    return ", ".join(f"{name}: {value}" for name, value in _fields_of(body))


def _fields_of(
    body:   Mapping[str, Any],  # np. {"returned": {"to_line": 14}, "lines": [{…}, {…}]}
    prefix: str = "",           # np. "returned." — ścieżka grupy, w której leżą pola
) -> Iterator[tuple[str, str]]:
    """
    Description:
    Oddaje po kolei pola wyniku narzędzia jako pary „ścieżka pola, wartość do wypisania". Grupę
    (obiekt w obiekcie) rozwija, dopisując jej nazwę do ścieżki; listę zamienia na liczbę
    pozycji, a tekst dłuższy niż `MAX_RESULT_TEXT_CHARS` na jego długość.

    Example args:
        body={"returned": {"to_line": 14, "end_of_file": True}, "lines": [{…}, {…}]}
        prefix=""

    Example result:
        ("returned.to_line", "14"), ("returned.end_of_file", "true"), ("lines", "2")
    """
    for name, value in body.items():
        path = f"{prefix}{name}"

        # --- grupa pól: jej pola pod pełną ścieżką ---
        if isinstance(value, dict):
            yield from _fields_of(value, prefix=f"{path}.")
        # --- lista: sama liczba pozycji ---
        elif isinstance(value, list):
            yield path, str(len(value))
        # --- długi tekst: sama długość, bez treści ---
        elif isinstance(value, str) and len(value) > MAX_RESULT_TEXT_CHARS:
            yield path, f"{len(value)} zn."
        # --- krótki tekst: bez cudzysłowów ---
        elif isinstance(value, str):
            yield path, value
        # --- liczba, flaga albo brak wartości: w zapisie JSON-a (`true`, `null`) ---
        else:
            yield path, json.dumps(value)
