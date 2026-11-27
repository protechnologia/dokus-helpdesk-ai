"""
Description:
Spójność zestawu tekstowego (`data/unsafe/golden/tool-tickets-text.json`) z kartami i wątkami golden
setu, bez stacku. Na zestawie stoi pomiar `find_tickets_text`, a zapytania i cele dobiera się
ręcznie: pomyłka w nich nie daje błędu, tylko fałszywy wynik pomiaru.

| warunek                                                  | czym grozi jego brak                 |
|----------------------------------------------------------|--------------------------------------|
| liczniki w metryczce zgadzają się z listami              | metryczka, która kłamie o zestawie   |
| cel to karta przyjęta przez filtr i ma wątek             | zapytanie o cel spoza tabeli         |
| fraza typowego zapytania stoi w wątku celu               | chybienie, które jest błędem zestawu |
| fraza zapytania bez celu nie stoi w żadnym wątku         | trafienie, które jest poprawne       |
| zapytanie ma frazę albo słowa i znaną warstwę            | zapytanie, którego narzędzie nie     |
|                                                          | przyjmie, albo warstwa z literówką   |
| zapytanie trudne mówi, jaką słabość sprawdza             | chybienie, którego nikt nie wyjaśni  |

Zestaw i korpus to dane klientów, poza repo, więc bez nich testy się pomija, a nie padają.
"""

import pytest

from app.core_service.filter_ticket_quality import filter_tickets
from tests._helpers.golden_tickets import (
    CORPUS_DIR,
    TEXT_FILE,
    TEXT_QUERY_KINDS,
    THREADS_DIR,
    contains_phrase,
    corpus,
    golden_text_set,
    golden_thread,
)

pytestmark = pytest.mark.skipif(
    not TEXT_FILE.is_file() or not CORPUS_DIR.is_dir() or not THREADS_DIR.is_dir(),
    reason="zestawu tekstowego i korpusu golden setu nie ma w repo",
)


def test_the_counts_in_the_metadata_match_the_lists() -> None:
    """Sprawdza, czy liczniki z metryczki — zapytania z celem i bez celu — zgadzają się z tym,
    co stoi w listach.

    Wyłapuje zapytanie dopisane bez poprawienia metryczki: opis zestawu i progi testu mówiłyby
    o innej liczbie zapytań niż ta, którą test mierzy."""
    text_set = golden_text_set()
    counts   = {
        "queries":     len(text_set.queries),
        "distractors": len(text_set.distractors),
    }

    assert text_set.counts == counts


def test_every_target_is_an_indexed_ticket_with_a_thread() -> None:
    """Sprawdza, czy celem każdego zapytania jest zgłoszenie, którego kartę przyjął filtr jakości
    i którego wątek leży w `anonymized/`, czyli takie, które jest w tabeli wątków golden setu.

    Wyłapuje cel, który do tabeli nie wchodzi: zapytanie liczyłoby się jako chybione, choć
    narzędzie działa, a próg z równym zapasem by tego nie pokazał."""
    kept    = {verdict.ticket_id for verdict in filter_tickets(corpus()).kept}
    threads = {path.stem for path in THREADS_DIR.glob("*.txt")}
    targets = {query.ticket_id for query in golden_text_set().queries}

    assert targets - kept == set()
    assert targets - threads == set()


def test_the_phrase_of_every_typical_query_stands_in_its_target_thread() -> None:
    """Sprawdza, czy fraza każdego zapytania typowego stoi w wątku jego celu tak, jak szuka jej
    podciąg w bazie: bez względu na wielkość liter i łamanie linii.

    Wyłapuje frazę przepisaną z literówką albo z wątku innego zgłoszenia: chybienie wyglądałoby
    jak słabość narzędzia, a byłoby błędem zestawu."""
    broken = [
        query.ticket_id
        for query in golden_text_set().queries
        if query.difficulty == "typowe"
        and query.exact is not None
        and not contains_phrase(golden_thread(query.ticket_id), query.exact)
    ]

    assert broken == []


def test_no_distractor_phrase_stands_in_any_golden_thread() -> None:
    """Sprawdza, czy fraza żadnego zapytania bez celu nie stoi w żadnym z 200 wątków golden
    setu.

    Wyłapuje zapytanie bez celu, które ma cel: trafienie na nie liczyłoby się jako pomyłka
    narzędzia, choć narzędzie znalazłoby to, co trzeba."""
    threads = [path.read_text(encoding="utf-8") for path in THREADS_DIR.glob("*.txt")]
    present = [
        query.exact
        for query in golden_text_set().distractors
        if any(contains_phrase(thread, query.exact) for thread in threads)
    ]

    assert len(threads) == 200
    assert present == []


def test_every_query_has_something_to_search_and_a_known_layer() -> None:
    """Sprawdza, czy każde zapytanie, z celem i bez celu, ma frazę albo słowa, a jego warstwa
    należy do znanych (kod, komunikat z ekranu, komunikat z logu, nazwa).

    Wyłapuje zapytanie, które narzędzie odrzuci jako puste, i literówkę w warstwie, która przy
    liczeniu osobno po warstwach stałaby jako osobna warstwa z jednym zapytaniem."""
    text_set = golden_text_set()
    broken   = [
        query
        for query in text_set.queries + text_set.distractors
        if not (query.exact or query.words) or query.kind not in TEXT_QUERY_KINDS
    ]

    assert broken == []


def test_every_hard_query_says_what_it_checks() -> None:
    """Sprawdza, czy każde zapytanie trudne ma niepustą notatkę, a typowe nie ma żadnej.

    Wyłapuje chybienie zapisane w progu bez wyjaśnienia: przy zmianie liczby nikt nie wiedziałby,
    czy to poprawa narzędzia, czy błąd."""
    broken = [
        query.ticket_id
        for query in golden_text_set().queries
        if (query.difficulty == "trudne") != bool(query.note and query.note.strip())
        or query.difficulty not in ("typowe", "trudne")
    ]

    assert broken == []
