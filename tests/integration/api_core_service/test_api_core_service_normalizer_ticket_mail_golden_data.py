"""
Description:
Spójność golden setu kanału „Automat mailowy” (`tickets-mail.json`) z wątkami, z których powstał,
bez modelu i bez stacku. Wpis to wątek: etykiety z 32.1 i pola, każde z autorem i oznaczeniami
linii z 32.3. Na zestawie stoi test ewaluacyjny normalizera maili, a pomyłka w nim nie daje
błędu, tylko fałszywy wynik pomiaru.

| warunek                                                 | czym grozi jego brak                   |
|---------------------------------------------------------|----------------------------------------|
| liczniki w metryczce zgadzają się z wpisami             | metryczka, która kłamie o zestawie     |
| wpis na każde pole wątku                                | pole pominięte w pomiarze              |
| skrót pola zgadza się z tekstem z `message_texts()`     | etykiety porównywane z przesuniętymi   |
|                                                         | liniami po zmianie czytnika eksportu   |
| etykieta na każdą linię ze słowami, żadnej ponad        | linie bez oceny albo oceny bez linii   |

Golden set i wątki to dane klientów, poza repo, więc bez nich testy się pomija, a nie padają.
"""

import json
from collections import Counter

import pytest

from app.core_service.normalizer_ticket_mail import message_texts
from app.core_util.repetition import words_of
from tests._helpers.golden_mail import (
    GOLDEN_FILE,
    LABELS,
    RAW_DB_DIR,
    GoldenMailTicket,
    field_digest,
    golden_mail_tickets,
    mail_thread,
)

pytestmark = pytest.mark.skipif(
    not GOLDEN_FILE.is_file() or not RAW_DB_DIR.is_dir(),
    reason="golden setu kanału mailowego i wątków źródłowych nie ma w repo",
)

# Zgłoszenia zestawu, po jednym teście pól na zgłoszenie; bez danych lista jest pusta, a testy
# pliku i tak pomija `pytestmark`.
TICKETS = golden_mail_tickets() if GOLDEN_FILE.is_file() else []


def test_the_counts_in_the_metadata_match_the_entries() -> None:
    """Sprawdza, czy liczniki z metryczki zgadzają się z wpisami pliku: wątki, sprawy,
    powiadomienia, z wiedzą i bez wiedzy, a także linie ze słowami i linie każdej etykiety.

    Wyłapuje etykietę zmienioną bez poprawienia metryczki: opis zestawu, liczby w CLAUDE.md
    i progi testów mówiłyby o innym zestawie niż ten, który mierzą."""
    raw     = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    tickets = golden_mail_tickets()
    kinds   = Counter(entry["kind"] for entry in raw["tickets"])
    useful  = sum(ticket.useful for ticket in tickets)
    labels  = Counter(
        label for ticket in tickets for field in ticket.fields for label in field.labels
    )
    counts  = {
        "tickets":       len(tickets),
        "sprawa":        kinds["sprawa"],
        "powiadomienie": kinds["powiadomienie"],
        "useful":        useful,
        "not_useful":    len(tickets) - useful,
        "lines":         sum(labels.values()),
        **{label: labels[label] for label in LABELS},
    }

    assert raw["meta"]["counts"] == counts


@pytest.mark.parametrize("ticket", TICKETS, ids=lambda ticket: ticket.ticket_id)
def test_every_field_has_its_author_and_labels(ticket: GoldenMailTicket) -> None:
    """Sprawdza, czy każde pole wątku (opis i komentarze) ma wpis z autorem, czy skrót tekstu
    pola się zgadza i czy etykiet jest tyle, ile linii ze słowami.

    Wyłapuje oznaczenia, które po zmianie czytnika eksportu albo `message_texts()` opisują inny
    tekst niż ten, który czyści normalizer: pomiar porównałby etykiety z przesuniętymi liniami
    i dałby wynik bez sensu."""
    texts = message_texts(mail_thread(ticket.ticket_id))

    assert [field.digest for field in ticket.fields] == [field_digest(text) for text in texts]
    assert [len(field.labels) for field in ticket.fields] == [
        sum(1 for line in text.split("\n") if words_of(line)) for text in texts
    ]
