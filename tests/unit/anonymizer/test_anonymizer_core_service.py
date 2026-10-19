import pytest

from anonymizer_app.core_model.found import Found
from anonymizer_app.core_service.analyzer_morphology import analyse_word
from anonymizer_app.core_service.finder_markers import marker_spans
from anonymizer_app.core_service.finder_word_forms import find_word_forms
from anonymizer_app.core_service.replacer_found import choose_found, replace_found
from anonymizer_app.core_util.spans import is_inside

# --- znaczniki ---


def test_marker_spans_and_inside() -> None:
    """Sprawdza, czy znaczniki w tekście dają swoje zakresy, a zakres w znaczniku leży w nim.

    Wyłapuje znacznik nierozpoznany, przez co słowo w nim („IMIĘ”) mogłoby zostać zamienione
    drugi raz."""
    spans = marker_spans("Pani {IMIĘ}, tel. {TELEFON}")

    assert spans == [(5, 11), (18, 27)]
    assert is_inside((6, 10), spans) is True
    assert is_inside((0, 4), spans) is False


# --- morfologia ---


@pytest.mark.parametrize(
    ("word", "lemma", "known", "proper_name"),
    [
        ("Ewie",       "ewa",   True,  True),
        ("Gądkiem",    "gądek", True,  True),
        ("Lista",      "lista", True,  False),
        ("Sobczakową", None,    False, False),
    ],
    ids=["imię", "nazwisko", "zwykłe-słowo", "spoza-słownika"],
)
def test_analyse_word_gives_lemmas_and_whether_it_is_a_person(
    word:        str,
    lemma:       str | None,
    known:       bool,
    proper_name: bool,
) -> None:
    """Sprawdza, czy analiza słowa daje jego lemat małymi literami (bez dopisków słownika), to,
    czy słownik je zna, i czy to imię albo nazwisko — a słowo spoza słownika ma pusty zbiór
    lematów.

    Wyłapuje odczyt kwalifikatora z niewłaściwej pozycji interpretacji (w pomiarze z 2026-10-19
    taka pomyłka wyłączyła regułę dla imion) i lemat z dopiskiem słownika („Lis:Sm1”), który nie
    zgodziłby się z żadnym innym."""
    analysis = analyse_word(word)

    assert analysis.known       is known
    assert analysis.proper_name is proper_name
    assert analysis.lemmas      == (frozenset({lemma}) if lemma else frozenset())


# --- odmiany wskazanego słowa ---


@pytest.mark.parametrize(
    ("text", "word", "expected"),
    [
        ("Pan Dudziak dzwonił. Przekazać Dudziakowi.", "Dudziak", ["Dudziak", "Dudziakowi"]),
        ("Pani Bronisławo, pani Bronisława", "Bronisławo", ["Bronisławo", "Bronisława"]),
        ("Kowalska i Kowalski", "Kowalski", ["Kowalska", "Kowalski"]),
        ("Pani Ewa, proszę przekazać Ewie.", "Ewa", ["Ewa", "Ewie"]),
        ("Pani Iza, czyli Izabela.", "Iza", ["Iza", "Izabela"]),
        ("Pani Sobczakową i Sobczakowej.", "Sobczakową", ["Sobczakową", "Sobczakowej"]),
        ("rozmawialem z panem fabisiakiem", "fabisiakiem", ["fabisiakiem"]),
        ("{NAZWISKO} Dudziak", "Dudziak", ["Dudziak"]),
        ("Al jest, Ala też.", "Al", []),
    ],
    ids=["dopełniacz", "wołacz", "rodzaj", "wymiana-głoski", "zdrobnienie", "spoza-słownika",
         "małe-litery", "znacznik", "za-krótkie"],
)
def test_find_word_forms_finds_every_form_of_a_person(
    text:     str,
    word:     str,
    expected: list[str],
) -> None:
    """Sprawdza, czy reguła znajduje każdą formę wskazanego imienia albo nazwiska: po wspólnym
    lemacie („Ewie” przy „Ewa”), po wspólnym początku na imię znane słownikowi („Izabela” przy
    zdrobnieniu „Iza”) i na słowo spoza słownika („Sobczakowej”), bez słów w znacznikach i bez
    słów krótszych niż trzy litery.

    Wyłapuje regułę, która zgubi odmianę: osoba podana przez model raz przeciekłaby wszędzie, gdzie
    stoi w innej formie. Sama reguła rdzenia gubiła „Ewie”, sam lemat — „Izabela”."""
    assert [text[start:end] for start, end in find_word_forms(text, word)] == expected


@pytest.mark.parametrize(
    ("text", "word", "expected"),
    [
        ("Pani Ala zgłasza: Alarm o dysku.", "Ala", ["Ala"]),
        ("Pan Lis. Lista jest pusta.", "Lis", ["Lis"]),
        ("Pan Lis, a lista jest pusta.", "Lis", ["Lis"]),
    ],
    ids=["alarm", "lista-z-wielkiej", "lista-z-małej"],
)
def test_find_word_forms_leaves_ordinary_words(
    text:     str,
    word:     str,
    expected: list[str],
) -> None:
    """Sprawdza, czy zwykłe słowo, które zaczyna się jak krótkie imię albo nazwisko („Alarm” przy
    „Ala”, „Lista” przy „Lis”, także na początku zdania), nie jest odmianą.

    Wyłapuje powrót samej reguły rdzenia: niszczyła „Lista zwrotów” i „Alarm o braku miejsca na
    dysku” w golden secie (s33), czyli wiedzę, której potem nikt z wątku nie odczyta."""
    assert [text[start:end] for start, end in find_word_forms(text, word)] == expected


def test_a_word_known_also_as_a_surname_is_still_caught() -> None:
    """Sprawdza i zapisuje znane ograniczenie: „Nowego” na początku zdania przy nazwisku „Nowak”
    zostaje wzięte za odmianę, bo słownik zna też nazwisko „Nowy”.

    Wyłapuje zmianę reguły, która po cichu zmienia tę granicę: test trzeba wtedy przepisać razem
    z opisem reguły, a nie dowiedzieć się o niej z korpusu. Pomyłka jest w stronę zamiany, nie
    przecieku."""
    text = "Pan Nowak. Nowego roku nie było."

    assert [text[start:end] for start, end in find_word_forms(text, "Nowak")] == ["Nowak", "Nowego"]


# --- wybór miejsc i zamiana ---


def test_the_longest_place_wins_and_ties_go_to_priority() -> None:
    """Sprawdza, czy z miejsc, które na siebie zachodzą, wygrywa dłuższe, a przy równej długości
    to z mniejszym priorytetem.

    Wyłapuje zamianę słowa z ulicy nazwanej od osoby na `{NAZWISKO}` wewnątrz adresu, który miał
    zniknąć w całości."""
    address = Found(kind="ADRES", start=0, end=22)
    surname = Found(kind="NAZWISKO", start=0, end=10)
    tie     = Found(kind="NAZWISKO", start=0, end=22)

    assert choose_found([(surname, 1), (address, 0)]) == [address]
    assert choose_found([(tie, 1), (address, 0)]) == [address]


def test_replace_found_swaps_places_for_markers() -> None:
    """Sprawdza, czy każde miejsce zamienia się na znacznik swojego rodzaju, a reszta tekstu
    zostaje bez zmian.

    Wyłapuje zamianę, która przesuwa pozycje kolejnych miejsc (zamiana od początku tekstu)."""
    text  = "Pani Bronisława, tel. 600 100 200"
    found = [Found(kind="IMIĘ", start=5, end=15), Found(kind="TELEFON", start=22, end=33)]

    assert replace_found(text, found) == "Pani {IMIĘ}, tel. {TELEFON}"
