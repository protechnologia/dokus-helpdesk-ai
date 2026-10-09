import pytest
from pydantic import ValidationError

from app.agent_tools.code.find_code_text import FindCodeTextQuery

# Model zapytania `find_code_text` odrzuca to, czego nie da się sensownie wyszukać w kodzie.
# Odrzucone zapytanie wraca do modelu jako błędne argumenty, zanim ruszy szukanie.


def test_a_phrase_words_or_both_make_a_query() -> None:
    """Sprawdza, czy zapytanie da się zbudować z samej frazy, z samych słów i z obu naraz,
    także ze ścieżką zawężenia.

    Wyłapuje model, który wymaga dokładnie jednego pola: wyszukiwania tekstowe zgłoszeń
    i dokumentacji przyjmują oba, więc model traciłby turę na błąd, pytając trzecie tak samo."""
    phrase = FindCodeTextQuery(exact="Brak sekwencji numeracji")
    words  = FindCodeTextQuery(words="sekwencji numeracji")
    both   = FindCodeTextQuery(exact="Brak sekwencji", words="sekwencji numeracji", path="src/lib")

    assert (phrase.exact, phrase.words, phrase.path) == ("Brak sekwencji numeracji", None, None)
    assert words.words                               == "sekwencji numeracji"
    assert (both.exact, both.words, both.path)       == ("Brak sekwencji", "sekwencji numeracji",
                                                         "src/lib")


@pytest.mark.parametrize("query", [{}, {"path": "src/web/js"}], ids=["puste", "sama ścieżka"])
def test_a_query_without_phrase_and_words_is_refused(query: dict[str, str]) -> None:
    """Sprawdza, czy zapytanie bez frazy i bez słów jest odrzucane, także gdy podaje ścieżkę.

    Wyłapuje puste szukanie, które oddałoby pustą listę: wyglądałaby ona jak „takiego tekstu
    nie ma w kodzie", choć model o nic nie zapytał."""
    with pytest.raises(ValidationError, match="exact, words"):
        FindCodeTextQuery(**query)


def test_the_edges_of_phrase_and_words_are_trimmed() -> None:
    """Sprawdza, czy spacje z początku i końca frazy oraz słów są obcinane.

    Wyłapuje frazę szukaną razem ze spacją z brzegu: komunikat przeklejony ze spacją na końcu
    nie znalazłby linii, w której po nim stoi apostrof."""
    query = FindCodeTextQuery(exact="  Brak sekwencji  ", words="  sekwencji numeracji ")

    assert query.exact == "Brak sekwencji"
    assert query.words == "sekwencji numeracji"


@pytest.mark.parametrize("exact", ["ab", " ab ", "   "], ids=["dwa znaki", "ze spacjami", "spacje"])
def test_a_phrase_shorter_than_three_characters_is_refused(exact: str) -> None:
    """Sprawdza, czy fraza, która po obcięciu spacji ma mniej niż trzy znaki, jest odrzucana.

    Wyłapuje frazę z dwóch znaków albo z samych spacji: w kodzie pasuje do setek tysięcy linii,
    więc wynik niczego by nie mówił, a szukanie zajęłoby sekundy."""
    with pytest.raises(ValidationError):
        FindCodeTextQuery(exact=exact)


def test_words_need_one_word_of_three_characters() -> None:
    """Sprawdza, czy słowa, z których żadne nie ma trzech znaków, są odrzucane z komunikatem
    o tym wymogu, a wystarcza jedno słowo tej długości obok krótkich.

    Wyłapuje szukanie po samych krótkich słowach, jak „do if": pierwsze z nich idzie do ripgrepa
    i pasuje do większości linii kodu."""
    with pytest.raises(ValidationError, match="co najmniej jedno słowo"):
        FindCodeTextQuery(words="do if")

    assert FindCodeTextQuery(words="do limitu").words == "do limitu"


@pytest.mark.parametrize(
    "query",
    [{"exact": "Brak\0sekwencji"}, {"words": "sekwencji\0 numeracji"}],
    ids=["we frazie", "w słowach"],
)
def test_a_null_character_is_refused(query: dict[str, str]) -> None:
    """Sprawdza, czy fraza albo słowa ze znakiem zerowym są odrzucane.

    Wyłapuje znak zerowy przepuszczony do uruchomienia programu: nie da się go przekazać jako
    argumentu, więc szukanie kończyłoby się błędem serwera zamiast odpowiedzią dla modelu."""
    with pytest.raises(ValidationError, match="znak zerowy"):
        FindCodeTextQuery(**query)


def test_an_empty_path_is_refused() -> None:
    """Sprawdza, czy pusta ścieżka zawężenia jest odrzucana.

    Wyłapuje pusty napis wzięty za „szukaj wszędzie": model, który chciał zawęzić szukanie
    i podał pustą wartość, dostałby wynik z całego kodu bez żadnego sygnału."""
    with pytest.raises(ValidationError):
        FindCodeTextQuery(exact="Brak sekwencji", path="")


def test_an_unknown_argument_is_refused() -> None:
    """Sprawdza, czy argument spoza modelu, na przykład `limit`, kończy się błędem walidacji.

    Wyłapuje model, który po cichu pomija wymyślony argument: model językowy uznałby, że sam
    ustawił długość wyniku, a tę ustala narzędzie."""
    with pytest.raises(ValidationError):
        FindCodeTextQuery(exact="Brak sekwencji", limit=5)
