"""
Description:
Test ewaluacyjny normalizera wątków kanału „Automat mailowy” (p. 32.3) na 136 wątkach golden
setu ze słownikiem maili instancji: role wobec autorów z 32.1 i linie wobec oznaczeń linii.

| co mierzy                                             | próg            | zmierzone dziś |
|-------------------------------------------------------|-----------------|----------------|
| pola, w których normalizer oddał co innego niż pomiar | 0               | 0              |
| role zgodne z autorami z 32.1                         | co najmniej 95% | 96,2%          |
| słowa, które zostają                                  | najwyżej 30%    | 27,5%          |
| linie treści usunięte w wątkach z wiedzą              | najwyżej 3      | 3              |
| słowa treści usunięte we wszystkich wątkach           | najwyżej 2%     | 1,0%           |
| śmieci (kopia, stopka) wśród słów, które zostały      | najwyżej 20%    | 18,7%          |

Po co: czyszczenie stoi przed anonimizatorem, więc może zaszkodzić na dwa sposoby, których nie
widać w samym tekście. Usunięta linia treści to wiedza, której nie dostanie ani karta, ani
model; zostawiony cytat albo stopka to dłuższy tekst z nazwiskami i adresami dla Bielika.
Udział słów, które zostają, sam niczego nie rozstrzyga: dopiero oznaczenia mówią, co zostało.

Co się dzieje po drodze (`measure_mail_cleaning()` z `tests/_helpers/golden_mail/`):

1. Dla każdego wątku z `data/unsafe/corpus/raw-db/` uruchamia normalizer ze słownikiem
   z `data/unsafe/mail/` i porównuje role pól z autorami z `tickets-mail.json`.
2. Pyta `repeated_lines()`, które linie zniknęły, i sprawdza, że normalizer oddał dokładnie
   słowa linii, które zostały.
3. Liczy linie i słowa każdej etykiety z oznaczeń linii w `tickets-mail.json`: które zostały,
   które zniknęły.

O czym pamiętać przy zmianach:

- `data/` nie ma w repo (PII), więc bez zestawu, wątków albo słownika test się pomija.
- Progi stoją obok zmierzonych liczb z małym zapasem. Słownik szablonów przebudowuje się po
  przyroście korpusu, a nowy słownik przesuwa liczby, choć metoda się nie zmienia.
- Metodę stroiliśmy na tych samych 136 wątkach, więc wynik jest optymistyczny.
- Oznaczenia linii robili oceniający na ślepo, a druga, niezależna ocena próbki 40 wątków
  zgadza się z pierwszą w 99,6% linii, więc progi mierzą czyszczenie, a nie szum oznaczeń.
- Trzy linie treści w wątku z wiedzą to znany koszt: masowy mail dostawcy z 12 wątków jest
  w całości szablonem, więc znika jego tło, a dopisane do niego zdanie z wiedzą zostaje.
"""

import pytest

from tests._helpers.golden_mail import (
    CONTENT_LABEL,
    GOLDEN_FILE,
    JUNK_LABELS,
    MAIL_DIR,
    MAX_JUNK_SHARE,
    MAX_KEPT_WORD_SHARE,
    MAX_LOST_CONTENT_SHARE,
    MAX_LOST_LINES_IN_USEFUL,
    MIN_ROLE_SHARE,
    RAW_DB_DIR,
    MailCleaningMeasurement,
    measure_mail_cleaning,
)


@pytest.fixture(scope="module")
def measurement() -> MailCleaningMeasurement:
    """
    Description:
    Przepuszcza normalizer przez golden set kanału mailowego raz na cały plik. Bez zestawu,
    wątków albo słownika maili pomija testy, zamiast je wywalać.

    Example args:
        (brak)

    Example result:
        MailCleaningMeasurement(role_fields=367, role_matches=353, words_before=91332, …)
    """
    for path in (GOLDEN_FILE, RAW_DB_DIR, MAIL_DIR):
        if not path.exists():
            pytest.skip(f"brak {path} — dane klienta nie są w repo")

    return measure_mail_cleaning()


def test_the_measurement_counts_exactly_what_the_normalizer_returns(
    measurement: MailCleaningMeasurement,
) -> None:
    """Sprawdza, czy w każdym polu wszystkich 136 wątków normalizer oddał dokładnie słowa tych
    linii, które pomiar uznał za zostające.

    Wyłapuje normalizer, który dostał krok spoza `repeated_lines()` (inne cięcie, dodatkowy
    filtr): pomiar liczyłby wtedy straty i śmieci dla czyszczenia, którego normalizer już nie
    robi, a progi niżej przechodziłyby przy dowolnym wyniku."""
    assert measurement.mismatched == ()


def test_roles_follow_the_signatures(measurement: MailCleaningMeasurement) -> None:
    """Sprawdza, czy rola ustalona z podpisu zgadza się z autorem z 32.1 w co najmniej 95% pól
    (dziś 353 z 367, 96,2%).

    Wyłapuje regułę autora, która przestała widzieć podpis dostawcy (np. po zmianie nazwy
    w `nazwy.json` albo granicy cytatu): odpowiedzi konsultantów wróciłyby do modelu jako
    wypowiedzi klienta, jak w surowej bazie."""
    assert measurement.role_matches / measurement.role_fields >= MIN_ROLE_SHARE


def test_most_of_the_text_goes(measurement: MailCleaningMeasurement) -> None:
    """Sprawdza, czy po czyszczeniu zostaje najwyżej 30% słów wątków (dziś 27,5%).

    Wyłapuje czyszczenie, które przestało działać po cichu (pusty albo nieaktualny słownik,
    zepsute powtórzenia): anonimizator dostałby znów kilka razy dłuższe wątki z cytatami
    i stopkami."""
    assert measurement.words_after / measurement.words_before <= MAX_KEPT_WORD_SHARE


def test_content_survives_in_threads_with_knowledge(measurement: MailCleaningMeasurement) -> None:
    """Sprawdza, czy w wątkach z wiedzą czyszczenie usuwa najwyżej 3 linie treści (dziś 3: tło
    masowego maila dostawcy w jednym wątku).

    Wyłapuje czyszczenie, które zaczyna wycinać nowe wypowiedzi: karta zgłoszenia z wiedzą
    straciłaby właśnie to, co ją do indeksu kwalifikuje."""
    assert measurement.lost_in_useful <= MAX_LOST_LINES_IN_USEFUL


def test_little_content_is_lost(measurement: MailCleaningMeasurement) -> None:
    """Sprawdza, czy we wszystkich wątkach czyszczenie usuwa najwyżej 2% słów treści (dziś 1,0%,
    prawie w całości ten sam masowy mail w 12 wątkach).

    Wyłapuje zbyt agresywne czyszczenie (krótszy ciąg powtórzenia, niższy próg słownika):
    wycinałoby zwroty i zdania z nowych wiadomości, także w wątkach bez wiedzy, po których
    filtr ocenia, czy wiedzy rzeczywiście nie ma."""
    content = measurement.by_label[CONTENT_LABEL]
    lost    = content.removed_words / (content.kept_words + content.removed_words)

    assert lost <= MAX_LOST_CONTENT_SHARE


def test_little_junk_is_left(measurement: MailCleaningMeasurement) -> None:
    """Sprawdza, czy wśród słów, które zostały, kopii i stopek jest najwyżej 20% (dziś 18,7%,
    głównie stopki urzędów przy pierwszym wystąpieniu).

    Wyłapuje czyszczenie, które zostawia cytaty albo stopki ze słownika: model i anonimizator
    czytaliby powtórzenia i formułki z nazwiskami i adresami zamiast samej treści."""
    junk = sum(measurement.by_label[label].kept_words for label in JUNK_LABELS)

    assert junk / measurement.words_after <= MAX_JUNK_SHARE
