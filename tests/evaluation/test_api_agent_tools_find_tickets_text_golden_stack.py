"""
Description:
Test ewaluacyjny narzędzia `find_tickets_text` na golden secie: czy narzędzie w konfiguracji,
z jaką jedzie produkt, oddaje agentowi zgłoszenie, z którego wątku pochodzi komunikat albo kod,
i czy na komunikaty, których w wątkach nie ma, nie oddaje nic. Wymaga działającego stacku
z tabelą wątków golden setu.

| co mierzy                                              | oczekiwane (2026-11-15) |
|--------------------------------------------------------|-------------------------|
| zapytania, na które zgłoszenie-cel wraca jako pierwsze | 21 z 23                 |
| zapytania, na które zgłoszenie-cel w ogóle wraca       | 22 z 23                 |
| zapytania bez celu, które dostają choć jedno trafienie | 0 z 6                   |

Po co: narzędzie składa się z kilku ogniw (podciąg z ujednoliconymi białymi znakami, słowa przez
polski słownik, łączenie wyników frazą przed słowami, limit) i każde da się zepsuć tak, że nic nie
padnie. Testy integracyjne chodzą na pięciu zmyślonych wątkach; tu ścieżka idzie przez wątki
prawdziwych zgłoszeń po anonimizacji.

Co się dzieje po drodze:

1. `measure_tickets_text()` z `tests/_helpers/golden_tickets/` sprawdza, że tabela
   `tickets_text_golden` trzyma dokładnie wątki kart golden setu przyjętych przez filtr jakości.
2. Każde zapytanie z `data/unsafe/golden/tool-tickets-text.json` (23 z celem, 6 bez celu) idzie do
   `FindTicketsTextTool` polami `exact` i `words`, z `RAG_TOP_K` z konfiguracji.
3. Liczy, ile razy cel wrócił jako pierwszy, ile razy wrócił w ogóle i ile zapytań bez celu
   dostało choć jedno trafienie.

O czym pamiętać przy zmianach:

- Test porównuje liczby dokładnie, a nie progiem: tabela jest zamrożona, a szukanie
  deterministyczne, więc każda zmiana w dowolną stronę to zmiana w narzędziu, w bazie albo
  w zestawie. Próg „co najmniej” nie złapałby pomiaru, który zawyża wynik.
- Dwa zapytania nie trafiają celu na pierwszym miejscu celowo (`difficulty: trudne`): częsty
  komunikat, którego wątek-cel jest najstarszy, i fraza bez polskich znaków. Druga z nich nie
  wraca wcale. Poprawa narzędzia w tych miejscach zmienia liczby i wymaga ich poprawienia
  w `constants.py` helpera.
- Trzy zapytania rozróżniają ścieżki, których zwykłe zapytania nie rozróżniają: fragment kodu
  znajduje tylko podciąg, fraza bez celu ma wszystkie słowa w innym wątku, a fraza ze słowami
  kontekstu stawia cel pierwszy tylko przy frazie przed słowami.
- Golden200 ma mało komunikatów, a te, które ma, są prawie unikalne: liczby pilnują ścieżki,
  skutecznością produktu nie są (pełny golden z korpusu importu to p. 79).
- Tabelę buduje `QDRANT_COLLECTION=tickets_golden POSTGRES_TICKETS_TABLE=tickets_text_golden
  helpdesk tickets reindex data/unsafe/golden`; test jej nie buduje.
- `data/` nie ma w repo (PII), więc bez zestawu test się pomija, a nie pada.
"""

import asyncio

import pytest

from tests._helpers.golden_tickets import (
    TEXT_DISTRACTORS_WITH_HITS,
    TEXT_FILE,
    TEXT_TARGET_FIRST,
    TEXT_TARGET_RETURNED,
    THREADS_DIR,
    TicketsTextMeasurement,
    measure_tickets_text,
)
from tests.conftest import build_host_settings, build_postgres_client

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_postgres,
]


@pytest.fixture(scope="module")
def measurement() -> TicketsTextMeasurement:
    """
    Description:
    Robi pomiar raz na cały plik. Bez zestawu albo wątków golden setu pomija testy, zamiast je
    wywalać.

    Example args:
        (brak)

    Example result:
        TicketsTextMeasurement(target_first=21, target_returned=22, distractors_with_hits=0)
    """
    if not TEXT_FILE.is_file() or not THREADS_DIR.is_dir():
        pytest.skip(f"brak zestawu tekstowego ({TEXT_FILE.parent}) — dane nie są w repo")

    limit = build_host_settings().rag_top_k

    return asyncio.run(measure_tickets_text(build_postgres_client(), limit))


def test_the_expected_ticket_comes_back_first(measurement: TicketsTextMeasurement) -> None:
    """Sprawdza, czy wyszukiwanie tekstowe stawia zgłoszenie, z którego pochodzi komunikat albo
    kod, na pierwszym miejscu dokładnie dla 21 z 23 zapytań zestawu, tak jak w pomiarze.

    Wyłapuje zmianę kolejności trafień albo łączenia wyników (na przykład słowa przed frazą),
    przy której nic nie pada, tylko agent dostaje właściwe zgłoszenie dalej na liście."""
    assert measurement.target_first == TEXT_TARGET_FIRST, (
        f"cel wrócił jako pierwszy dla {measurement.target_first} zapytań, oczekiwane "
        f"{TEXT_TARGET_FIRST} — czy zmieniła się kolejność trafień albo łączenie frazy ze "
        f"słowami? Poprawa narzędzia też zmienia tę liczbę: wtedy popraw ją w helperze."
    )


def test_the_expected_ticket_is_found_by_phrase_and_by_words(
    measurement: TicketsTextMeasurement,
) -> None:
    """Sprawdza, czy właściwe zgłoszenie jest wśród zwróconych dokładnie dla 22 z 23 zapytań
    zestawu, także przy frazie złamanej między liniami, przy fragmencie kodu i przy słowach
    w innej odmianie niż w wątku.

    Wyłapuje zepsute ujednolicanie białych znaków, frazę szukaną słowami (fragment kodu wtedy
    ginie), słownik, który przestał odmieniać, i limit, który odcina zgłoszenie, którego agent
    szuka."""
    assert measurement.target_returned == TEXT_TARGET_RETURNED, (
        f"cel wrócił dla {measurement.target_returned} zapytań, oczekiwane "
        f"{TEXT_TARGET_RETURNED} — czy fraza idzie podciągiem, czy działa słownik `pl_search` "
        f"i czy zmieniło się `RAG_TOP_K`?"
    )


def test_messages_absent_from_the_threads_come_back_empty(
    measurement: TicketsTextMeasurement,
) -> None:
    """Sprawdza, czy komunikaty, których jako frazy nie ma w żadnym wątku golden setu, nie dają
    żadnego trafienia: wymagane 0 z 6.

    Wyłapuje szukanie, które dopasowuje za luźno (na przykład frazę po pojedynczych słowach):
    agent dostałby zgłoszenia bez związku z komunikatem, a one wyglądają na odpowiedź."""
    assert measurement.distractors_with_hits == TEXT_DISTRACTORS_WITH_HITS, (
        f"trafienie dostało {measurement.distractors_with_hits} zapytań bez celu, oczekiwane "
        f"{TEXT_DISTRACTORS_WITH_HITS} — fraza dopasowuje się za luźno"
    )
