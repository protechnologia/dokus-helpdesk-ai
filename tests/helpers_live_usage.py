"""
Description:
Raport zużycia żywego, płatnego modelu w testach `llm_live`: zbiera zużycie każdej sprawy
i składa podsumowanie, które pytest wypisuje na końcu przebiegu — linię na sprawę, pod nią
przebieg grafu, a na końcu sumę kosztu.

| co                | do czego                                                          |
|-------------------|-------------------------------------------------------------------|
| `LiveUsageReport` | raport: `record()` dopisuje sprawę, `lines()` składa podsumowanie |
| `LiveUsage`       | jedna zgłoszona sprawa: etykieta, zużycie i wpisy przebiegu       |
| `usage_as_text()` | zużycie jedną linią dla człowieka                                 |

Przykład — dwie sprawy i to, co pytest wypisze po przebiegu:

    report.record("graf search", state.usage, state.log)
    report.record("complete: zwykłe pytanie", usage)

    graf search: wywołań 5, świeże wejście 412, zapis do cache 8120, odczyt z cache 25010, …
        agent: tura 1: narzędzia: find_code_text; 0,0041 USD
        run_tools: wywołania: find_code_text; źródła: 0
    complete: zwykłe pytanie: wywołań 1, świeże wejście 30, zapis do cache 0, …
    RAZEM: wywołań 6, …, koszt 0,0272 USD

O czym pamiętać przy zmianach:

- Raport dostaje się przez fixture `live_usage` z `tests/conftest.py`, jeden na cały przebieg.
  Tam też stoi funkcja, która go wypisuje: pytest szuka fixture'ów i swoich haków tylko
  w `conftest.py`. Obiekt zbudowany w teście nie trafiłby do podsumowania.
- Sumę liczy się z pola `usage` każdej sprawy. Wpisy `log` są tylko wypisywane: to tekst dla
  człowieka, z którego liczb się nie wyciąga.
- Sprawa zakończona błędem nie oddaje stanu, więc jej zużycia w raporcie nie ma.
"""

import dataclasses
import functools
from collections.abc import Sequence

from app.agent_nodes.models import LogEntry
from app.engine_llm import LLMUsage


@dataclasses.dataclass(frozen=True)
class LiveUsage:
    """Zużycie jednej sprawy na żywym modelu, zgłoszone przez test."""

    label: str                   # np. "graf search"
    usage: LLMUsage              # wywołania, tokeny i koszt całej sprawy
    log:   tuple[LogEntry, ...]  # wpisy przebiegu grafu; puste, gdy sprawa nie szła przez graf


class LiveUsageReport:
    """
    Description:
    Zbiera zużycie spraw przeprowadzonych na żywym, płatnym modelu w jednym przebiegu pytesta
    i składa z niego podsumowanie: linię na sprawę, pod nią przebieg grafu, a na końcu sumę.

    Do czego:
    Testy `llm_live` sprawdzają okablowanie, ale każdy ich przebieg kosztuje. Bez tego
    podsumowania koszt trzeba było liczyć osobno, a tego, których narzędzi model użył, nie było
    widać wcale.

    Flow:
        1. Test dostaje raport przez fixture `live_usage` i woła `record()` raz na sprawę —
           tam, gdzie liczy odpowiedź modelu.
        2. Po przebiegu `pytest_terminal_summary()` wypisuje `lines()`.

    Sumę liczy się z pola `usage` każdej sprawy. Wpisy `log` są tylko wypisywane: to tekst dla
    człowieka, z którego liczb się nie wyciąga.
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
        label: str,                     # np. "graf search"
        usage: LLMUsage,                # np. state.usage — zużycie całej sprawy
        log:   Sequence[LogEntry] = (), # np. state.log — wpisy przebiegu grafu
    ) -> None:
        """
        Description:
        Dopisuje do raportu jedną sprawę: jej zużycie i, jeśli szła przez graf, wpisy przebiegu.

        Example args:
            label="graf search"
            usage=LLMUsage(calls=5, prompt_tokens=412, cost_usd=0.027)
            log=[LogEntry(node="agent", message="tura 1: narzędzia: read_docs; 0,0041 USD")]

        Example result:
            None — sprawa jest w raporcie
        """
        self._records.append(LiveUsage(label=label, usage=usage, log=tuple(log)))

    def lines(self) -> list[str]:
        """
        Description:
        Składa podsumowanie: dla każdej sprawy linię z wywołaniami, tokenami w czterech klasach
        i kosztem, pod nią wcięte wpisy przebiegu grafu, a na końcu linię „RAZEM" z sumą.
        Pusty raport daje pustą listę.

        Example args:
            (brak)

        Example result:
            ["graf search: wywołań 5, świeże wejście 412, zapis do cache 8120, odczyt z cache "
             "25010, wyjście 640, koszt 0,0270 USD",
             "    agent: tura 1: narzędzia: read_docs; 0,0041 USD",
             "RAZEM: wywołań 5, świeże wejście 412, zapis do cache 8120, odczyt z cache 25010, "
             "wyjście 640, koszt 0,0270 USD"]
        """
        # --- nic nie zgłoszono: przebieg bez testów na żywym modelu ---
        if not self._records:
            return []

        lines: list[str] = []

        for record in self._records:
            lines.append(f"{record.label}: {usage_as_text(record.usage)}")
            lines.extend(f"    {entry.node}: {entry.message}" for entry in record.log)

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
