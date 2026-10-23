"""
Description:
Spójność golden setu zgłoszeń (`data/unsafe/golden/tickets.json`) z korpusem odniesienia, bez
stacku i bez modelu. Na tym pliku stoją dwa pomiary: wyszukiwania po znaczeniu (zapytania,
`find_tickets_vector`) i filtra jakości (etykiety `useful`). Etykiety i liczniki poprawia się
ręcznie, a pomyłka w nich nie daje błędu, tylko fałszywy wynik pomiaru.

| warunek                                              | czym grozi jego brak                    |
|------------------------------------------------------|-----------------------------------------|
| liczniki w metryczce zgadzają się z wpisami          | metryczka, która kłamie o zestawie      |
| pomiar wyszukiwania bierze policzone zapytania       | pomiar zapytań o cel spoza indeksu      |
| każde zgłoszenie korpusu ma dokładnie jeden wpis     | rekord bez etykiety albo z dwiema       |
| najpierw wpisy z wiedzą, potem bez, w obu po numerze | plik, którego nie da się przejrzeć      |
| każda etykieta ma uzasadnienie                       | etykieta, której nikt nie sprawdzi      |
| zapytanie ma tekst i znaną warstwę                   | warstwa liczona osobno w pomiarze       |
|                                                      | embeddera, której nie ma                |

Golden set i korpus to dane klientów, poza repo, więc bez nich testy się pomija, a nie padają.
"""

import pytest

from tests._helpers.golden_tickets import (
    CORPUS_DIR,
    GOLDEN_FILE,
    QUERY_DIFFICULTIES,
    QUERY_KINDS,
    corpus,
    golden_queries,
    golden_set,
)

pytestmark = pytest.mark.skipif(
    not GOLDEN_FILE.is_file() or not CORPUS_DIR.is_dir(),
    reason="golden setu i korpusu odniesienia nie ma w repo",
)


def test_the_counts_in_the_metadata_match_the_entries() -> None:
    """Sprawdza, czy liczniki z metryczki — wpisy z wiedzą, bez wiedzy i zapytania przy wpisach
    z wiedzą — zgadzają się z tym, co stoi w liście wpisów.

    Wyłapuje etykietę zmienioną bez poprawienia metryczki: opis zestawu i progi testów, które się
    na nim opierają, mówiłyby o innym zestawie niż ten, który mierzą."""
    golden = golden_set()
    useful = [ticket for ticket in golden.tickets if ticket.useful]
    counts = {
        "useful":     len(useful),
        "not_useful": len(golden.tickets) - len(useful),
        "queries":    sum(ticket.query is not None for ticket in useful),
    }

    assert golden.counts == counts


def test_the_search_measurement_takes_exactly_the_counted_queries() -> None:
    """Sprawdza, czy pomiar wyszukiwania bierze tyle zapytań, ile metryczka liczy przy wpisach
    z wiedzą, i czy celem każdego z nich jest wpis z wiedzą.

    Wyłapuje pomiar, który bierze też zapytania stojące przy wpisach bez wiedzy: ich celu filtr
    nie wpuszcza do indeksu, więc każde liczyłoby się jako chybione, a przy progach z zapasem
    nic by nie padło, tylko liczby przestałyby znaczyć to, co mówi opis testu."""
    golden  = golden_set()
    useful  = {ticket.ticket_id for ticket in golden.tickets if ticket.useful}
    targets = [target for target, _query in golden_queries()]

    assert len(targets) == golden.counts["queries"]
    assert set(targets) <= useful


def test_every_corpus_ticket_has_exactly_one_entry() -> None:
    """Sprawdza, czy numery wpisów się nie powtarzają i są dokładnie numerami kart korpusu
    odniesienia.

    Wyłapuje wpis zgubiony albo zdublowany przy przenoszeniu etykiety i korpus podmieniony bez
    zestawu: filtr byłby mierzony na rekordach, których przegląd nie oznaczył."""
    ids = [ticket.ticket_id for ticket in golden_set().tickets]

    assert len(ids) == len(set(ids))
    assert set(ids) == {ticket.ticket_id for ticket in corpus()}


def test_entries_stand_useful_first_and_by_number() -> None:
    """Sprawdza, czy wpisy z wiedzą stoją przed wpisami bez wiedzy, a w obu grupach rosnąco po
    numerze zgłoszenia.

    Wyłapuje wpis dopisany na końcu albo przeniesiony bez przestawienia: przy dwustu wpisach
    przegląd etykiet idzie po kolejności, a nie po wyszukiwaniu."""
    tickets = golden_set().tickets
    order   = sorted(tickets, key=lambda ticket: (not ticket.useful, int(ticket.ticket_id)))

    assert tickets == order


def test_every_label_says_why() -> None:
    """Sprawdza, czy każdy wpis ma niepuste uzasadnienie etykiety.

    Wyłapuje etykietę bez powodu: przy rozjeździe z oceną modelu nie byłoby wiadomo, kto się
    myli, i trzeba by czytać wątek od nowa."""
    tickets = golden_set().tickets
    blank   = [ticket.ticket_id for ticket in tickets if not ticket.useful_reason.strip()]

    assert blank == []


def test_every_query_has_text_and_a_known_layer() -> None:
    """Sprawdza, czy każde zapytanie ma niepusty tekst we wszystkich trzech polach, a jego rodzaj
    i trudność należą do warstw, po których liczy `scripts/eval_embeddings.py`.

    Wyłapuje zapytanie z pustym polem narzędzia, które szukałoby samym objawem, i literówkę
    w warstwie, która w tabeli pomiaru stałaby jako osobny wiersz z jednym zapytaniem."""
    broken = [
        ticket.ticket_id
        for ticket in golden_set().tickets
        if ticket.query is not None
        and not (
            ticket.query.query_raw.strip()
            and ticket.query.query_problem.strip()
            and ticket.query.query_symptoms.strip()
            and ticket.query.kind in QUERY_KINDS
            and ticket.query.difficulty in QUERY_DIFFICULTIES
        )
    ]

    assert broken == []
