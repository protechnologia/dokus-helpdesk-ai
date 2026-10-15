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

Co się dzieje po drodze (`measure_filter()` z `tests/_helpers/golden_tickets/`):

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


import pytest

from tests._helpers.golden_tickets import (
    CORPUS_DIR,
    GOLDEN_FILE,
    MAX_FALSE_POSITIVES,
    MIN_LABELLED_DROPS,
    FilterMeasurement,
    measure_filter,
)


@pytest.fixture(scope="module")
def measurement() -> FilterMeasurement:
    """
    Description:
    Przepuszcza filtr przez korpus odniesienia raz na cały plik. Bez korpusu pomija testy, zamiast
    je wywalać.

    Example args:
        (brak)

    Example result:
        FilterMeasurement(labelled_drops=29, false_positives=0)
    """
    if not CORPUS_DIR.is_dir() or not GOLDEN_FILE.is_file():
        pytest.skip(f"brak korpusu referencyjnego ({CORPUS_DIR}) — dane nie są w repo")

    return measure_filter()


def test_filter_still_recognises_hollow_records(measurement: FilterMeasurement) -> None:
    """Sprawdza, czy filtr jakości nadal odrzuca zgłoszenia bez wiedzy: z 38 rekordów, które przy
    ręcznym przeglądzie uznano za bezwartościowe, ma odrzucić co najmniej 25.

    Wyłapuje sytuację, w której po zmianie promptu parsującego albo modelu filtr przestaje
    cokolwiek odrzucać i puste rekordy trafiają do indeksu."""
    assert measurement.labelled_drops >= MIN_LABELLED_DROPS, (
        f"filtr odrzuca {measurement.labelled_drops} z zaetykietowanych rekordów, oczekiwane >= "
        f"{MIN_LABELLED_DROPS} — czy zmienił się prompt parsujący albo model?"
    )


def test_filter_does_not_reject_good_records(measurement: FilterMeasurement) -> None:
    """Sprawdza, czy filtr jakości nie wyrzuca dobrych zgłoszeń: ze 162 rekordów, które przy
    ręcznym przeglądzie uznano za dobre, wolno mu odrzucić najwyżej 2.

    Wyłapuje regułę filtra, która stała się za szeroka i po cichu usuwa z indeksu przydatne
    rekordy."""
    assert measurement.false_positives <= MAX_FALSE_POSITIVES, (
        f"filtr odrzucił {measurement.false_positives} rekordów uznanych za dobre, dozwolone "
        f"{MAX_FALSE_POSITIVES} — reguła stała się za szeroka"
    )
