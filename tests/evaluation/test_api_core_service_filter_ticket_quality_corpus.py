"""
Description:
Test ewaluacyjny filtra jakości na korpusie odniesienia (200 sparsowanych zgłoszeń): wynik filtra
porównuje z etykietami z ręcznego przeglądu tych samych rekordów.

| co mierzy                                     | próg           | zmierzone dziś |
|-----------------------------------------------|----------------|----------------|
| odrzucone spośród 38 oznaczonych „bez wiedzy" | co najmniej 25 | 29             |
| odrzucone spośród 162 uznanych za dobre       | najwyżej 2     | 0              |

Po co: reguły filtra czytają tekst pisany przez model, więc psują się przez zamilknięcie. Zmiana
fraz ucieczkowych w prompcie parsującym albo podmiana modelu i nagle nic nie pasuje — każdy rekord
przechodzi, indeks zapełnia się pustymi wpisami, a żaden inny test tego nie zauważy.

Co się dzieje po drodze:

1. Czyta 200 artefaktów z `data/unsafe/parsed/bielik-11b-golden200/`.
2. Czyta id rekordów oznaczonych w przeglądzie jako niosące zero wiedzy (`rejected`
   w `data/unsafe/golden/tickets-dokus.json`).
3. Uruchamia `filter_tickets()` i liczy, ile odrzuceń trafia w oznaczone, a ile poza nie.

O czym pamiętać przy zmianach:

- `data/` nie ma w repo (PII), więc bez korpusu test się pomija, a nie pada. To jedyny taki
  wyjątek w projekcie: tu warunek celowo nie jest dostarczany.
- Progi stoją obok zmierzonych wartości z zapasem: zwykły dryf nie ma wywalać testu, zamilknięcie
  filtra ma.
- Etykiety wytworzył model czytający te same artefakty, więc test mierzy zgodność z tamtym
  przeglądem, nie poprawność filtra.
"""

import json
from pathlib import Path

import pytest

from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_service.filter_ticket_quality import filter_tickets

# Korpus odniesienia i etykiety z jego przeglądu; oba mają przetrwać masowy import (p. 31).
CORPUS_DIR  = Path("data/unsafe/parsed/bielik-11b-golden200")
LABELS_FILE = Path("data/unsafe/golden/tickets-dokus.json")

# Zmierzone 29 z 38; próg niżej, żeby wyłapać filtr, który zamilkł, a nie zwykły dryf.
MIN_LABELLED_DROPS = 25

# Zmierzone 0. Fałszywy alarm jest droższą pomyłką: dobry rekord znika z indeksu niezauważony.
MAX_FALSE_POSITIVES = 2


def _load_corpus() -> list[ParsedTicket]:
    """
    Description:
    Czyta wszystkie artefakty korpusu odniesienia, w kolejności posortowanej.

    Example args:
        (brak)

    Example result:
        [ParsedTicket(ticket_id="10012", …), …]
    """
    tickets = [
        ParsedTicket.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(CORPUS_DIR.glob("*.json"))
    ]

    return tickets


def _load_rejected_ids() -> set[str]:
    """
    Description:
    Czyta id zgłoszeń, które przegląd oznaczył jako niosące zero wiedzy.

    Example args:
        (brak)

    Example result:
        {"19596", "27348", …}
    """
    labels = json.loads(LABELS_FILE.read_text(encoding="utf-8"))

    return {str(entry["ticket_id"]) for entry in labels["rejected"]}


@pytest.fixture(scope="module")
def measurement() -> tuple[int, int]:
    """
    Description:
    Przepuszcza filtr przez korpus odniesienia raz i zwraca parę: ile odrzuceń trafiło w rekordy
    oznaczone, ile w rekordy uznane za dobre. Bez korpusu pomija testy, zamiast je wywalać.

    Example args:
        (brak)

    Example result:
        (29, 0)
    """
    if not CORPUS_DIR.is_dir() or not LABELS_FILE.is_file():
        pytest.skip(f"brak korpusu referencyjnego ({CORPUS_DIR}) — dane nie są w repo")

    rejected = _load_rejected_ids()
    report   = filter_tickets(_load_corpus())
    dropped  = {verdict.ticket_id for verdict in report.dropped}

    labelled_drops  = len(dropped & rejected)
    false_positives = len(dropped - rejected)

    return labelled_drops, false_positives


def test_filter_still_recognises_hollow_records(measurement: tuple[int, int]) -> None:
    """Sprawdza, czy filtr jakości nadal odrzuca zgłoszenia bez wiedzy: z 38 rekordów, które przy
    ręcznym przeglądzie uznano za bezwartościowe, ma odrzucić co najmniej 25.

    Wyłapuje sytuację, w której po zmianie promptu parsującego albo modelu filtr przestaje
    cokolwiek odrzucać i puste rekordy trafiają do indeksu."""
    labelled_drops, _ = measurement

    assert labelled_drops >= MIN_LABELLED_DROPS, (
        f"filtr odrzuca {labelled_drops} z zaetykietowanych rekordów, oczekiwane >= "
        f"{MIN_LABELLED_DROPS} — czy zmienił się prompt parsujący albo model?"
    )


def test_filter_does_not_reject_good_records(measurement: tuple[int, int]) -> None:
    """Sprawdza, czy filtr jakości nie wyrzuca dobrych zgłoszeń: ze 162 rekordów, które przy
    ręcznym przeglądzie uznano za dobre, wolno mu odrzucić najwyżej 2.

    Wyłapuje regułę filtra, która stała się za szeroka i po cichu usuwa z indeksu przydatne
    rekordy."""
    _, false_positives = measurement

    assert false_positives <= MAX_FALSE_POSITIVES, (
        f"filtr odrzucił {false_positives} rekordów uznanych za dobre, dozwolone "
        f"{MAX_FALSE_POSITIVES} — reguła stała się za szeroka"
    )
