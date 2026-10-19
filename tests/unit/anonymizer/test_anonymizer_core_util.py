import pytest

from anonymizer_app.core_util.chunks import split_into_chunks
from anonymizer_app.core_util.fold import fold_text, fold_word
from anonymizer_app.core_util.spans import is_inside

# --- składanie słów ---


@pytest.mark.parametrize(
    ("word", "expected"),
    [("Wiśniewskiej", "wisniewskiej"), ("ŁUKASZ", "lukasz"), ("Michał", "michal")],
    ids=["ogonki", "wielkie-ł", "małe-ł"],
)
def test_fold_word_drops_case_and_polish_letters(word: str, expected: str) -> None:
    """Sprawdza, czy słowo składa się do małych liter bez polskich znaków, także z „ł” i „Ł”.

    Wyłapuje „ł”, którego rozkład Unicode nie zdejmuje: model podaje czasem nazwisko bez polskich
    znaków, a wtedy nie pasowałoby do zapisu w tekście."""
    assert fold_word(word) == expected


def test_fold_text_keeps_every_position() -> None:
    """Sprawdza, czy tekst złożony znak po znaku ma tę samą długość co oryginał, także ze znakiem,
    który składa się do dwóch („ß”).

    Wyłapuje przesunięcie pozycji: zakres dopasowany w złożonym tekście wskazywałby w oryginale
    nie te znaki, więc zamiana zjadłaby sąsiednie słowo."""
    text = "Straße 5, na Brzozowej 12"

    assert len(fold_text(text)) == len(text)
    assert fold_text(text)[-12:] == "brzozowej 12"


# --- części tekstu ---


def test_a_short_text_is_one_chunk() -> None:
    """Sprawdza, czy tekst, który mieści się w limicie, jest jedną częścią, bez zmian.

    Wyłapuje dzielenie zwykłego zgłoszenia: każda część to osobne wywołanie modelu."""
    assert split_into_chunks("Od: Leszek Dudziak", 6000) == ["Od: Leszek Dudziak"]


@pytest.mark.parametrize(
    "text",
    [
        "Od: Leszek Dudziak\nDo: kancelaria\nProszę o zmianę adresu.",
        "aaa bbb ccc ddd eee fff ggg hhh iii jjj\nkrótka",
        "x" * 75,
    ],
    ids=["linie", "długa-linia", "bez-odstępu"],
)
def test_chunks_fit_the_limit_and_join_back(text: str) -> None:
    """Sprawdza, czy każda część mieści się w limicie, a złączone dają tekst bez zmian — przy
    podziale po liniach, linii dłuższej niż limit i linii bez odstępu.

    Wyłapuje część ponad limit (serwer modelu odrzuciłby żądanie) i zgubiony albo zdublowany
    kawałek tekstu, w którym mogła stać osoba."""
    chunks = split_into_chunks(text, 30)

    assert all(len(chunk) <= 30 for chunk in chunks)
    assert "".join(chunks) == text
    assert len(chunks) > 1




# --- zakresy ---


def test_is_inside() -> None:
    """Sprawdza, czy zakres leżący w całości w którymś z podanych jest „w środku”, a zakres
    wychodzący poza każdy — nie.

    Wyłapuje odwrócone porównanie granic: słowo w znaczniku zostałoby zamienione drugi raz albo
    słowo obok znacznika pominięte."""
    assert is_inside((6, 10), [(5, 11)]) is True
    assert is_inside((4, 10), [(5, 11)]) is False
