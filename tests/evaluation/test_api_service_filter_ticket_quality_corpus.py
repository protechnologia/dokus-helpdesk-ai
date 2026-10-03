"""
Description:
Test ewaluacyjny rozpoznawania pustych pól na korpusie odniesienia (200 sparsowanych zgłoszeń):
filtr jakości porównuje z etykietami z ręcznego przeglądu tych samych rekordów, a rozpoznawanie
przyczyny nieustalonej z liczbą zmierzoną przy jego pisaniu.

| co mierzy                                      | próg           | zmierzone dziś |
|------------------------------------------------|----------------|----------------|
| odrzucone spośród 38 oznaczonych „bez wiedzy"  | co najmniej 25 | 29             |
| odrzucone spośród 162 uznanych za dobre        | najwyżej 2     | 0              |
| rekordy z przyczyną rozpoznaną jako nieustalona | co najmniej 85 | 98             |

Po co: reguły filtra czytają tekst pisany przez model, więc psują się przez zamilknięcie. Zmiana
fraz ucieczkowych w prompcie parsującym albo podmiana modelu i nagle nic nie pasuje — każdy rekord
przechodzi, indeks zapełnia się pustymi wpisami, a żaden inny test tego nie zauważy.

Co się dzieje po drodze:

1. Czyta 200 artefaktów z `data/parsed/bielik-11b-golden200/`.
2. Czyta id rekordów oznaczonych w przeglądzie jako niosące zero wiedzy (`rejected`
   w `data/golden/golden200.json`).
3. Uruchamia `filter_tickets()` i liczy, ile odrzuceń trafia w oznaczone, a ile poza nie.
4. Osobno liczy rekordy, w których `no_cause()` rozpoznaje przyczynę nieustaloną.

O czym pamiętać przy zmianach:

- `data/` nie ma w repo (PII), więc bez korpusu test się pomija, a nie pada. To jedyny taki
  wyjątek w projekcie: tu warunek celowo nie jest dostarczany.
- Progi stoją obok zmierzonych wartości z zapasem: zwykły dryf nie ma wywalać testu, zamilknięcie
  filtra ma.
- Etykiety wytworzył model czytający te same artefakty, więc test mierzy zgodność z tamtym
  przeglądem, nie poprawność filtra.
- Dla przyczyn nie ma etykiet, więc jest tylko dolny próg: łapie zamilknięcie, nie fałszywe
  trafienia.
"""

import json
from pathlib import Path

import pytest

from app.model.ticket_parsed import ParsedTicket
from app.service.filter_ticket_quality import filter_tickets
from app.service.normalizer_sentinel import no_cause

# Korpus odniesienia i etykiety z jego przeglądu; oba mają przetrwać masowy import (p. 31).
CORPUS_DIR  = Path("data/parsed/bielik-11b-golden200")
LABELS_FILE = Path("data/golden/golden200.json")

# Zmierzone 29 z 38; próg niżej, żeby wyłapać filtr, który zamilkł, a nie zwykły dryf.
MIN_LABELLED_DROPS = 25

# Zmierzone 0. Fałszywy alarm jest droższą pomyłką: dobry rekord znika z indeksu niezauważony.
MAX_FALSE_POSITIVES = 2

# Zmierzone 98 z 200; próg niżej z tego samego powodu co przy filtrze.
MIN_UNKNOWN_CAUSES = 85


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
    """Filtr na korpusie odniesienia → nadal odrzuca większość rekordów oznaczonych w przeglądzie:
    zmieniony prompt parsujący albo model nie może uciszyć reguł niezauważenie."""
    labelled_drops, _ = measurement

    assert labelled_drops >= MIN_LABELLED_DROPS, (
        f"filtr odrzuca {labelled_drops} z zaetykietowanych rekordów, oczekiwane >= "
        f"{MIN_LABELLED_DROPS} — czy zmienił się prompt parsujący albo model?"
    )


def test_filter_does_not_reject_good_records(measurement: tuple[int, int]) -> None:
    """Filtr na korpusie odniesienia → prawie żaden rekord uznany za dobry nie odpada: fałszywy
    alarm usuwa rekord z indeksu po cichu, a przepuszczony pusty tylko zajmuje miejsce."""
    _, false_positives = measurement

    assert false_positives <= MAX_FALSE_POSITIVES, (
        f"filtr odrzucił {false_positives} rekordów uznanych za dobre, dozwolone "
        f"{MAX_FALSE_POSITIVES} — reguła stała się za szeroka"
    )


def test_unknown_causes_are_still_recognised() -> None:
    """`no_cause()` na korpusie odniesienia → nadal rozpoznaje blisko połowę rekordów jako bez
    ustalonej przyczyny: gdyby zamilkło, blok przyczyn w `find_tickets_vector` pokazywałby „Brak
    ustalonej przyczyny…" jako przyczyny."""
    if not CORPUS_DIR.is_dir():
        pytest.skip(f"brak korpusu referencyjnego ({CORPUS_DIR}) — dane nie są w repo")

    unknown = sum(no_cause(ticket.cause) for ticket in _load_corpus())

    assert unknown >= MIN_UNKNOWN_CAUSES, (
        f"`no_cause()` rozpoznaje {unknown} rekordów, oczekiwane >= {MIN_UNKNOWN_CAUSES} — "
        f"czy zmienił się prompt parsujący albo model?"
    )
