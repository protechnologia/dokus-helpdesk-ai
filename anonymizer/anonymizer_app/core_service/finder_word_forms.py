"""
Description:
Odmiany wskazanego słowa w tekście: „Dudziak”, „Dudziaka” i „Dudziakowi” to jedno nazwisko,
„Ewa” i „Ewie” — jedno imię. Model wskazuje osobę w jednej formie, a w wątku stoi ona w kilku;
bez tej reguły zamieniłaby się tylko forma, którą model podał, a reszta przeszłaby do modelu
zewnętrznego.

Reguła — słowo w tekście jest odmianą wskazanego, gdy:

1. ma z nim wspólny lemat w słowniku (`analyse_word()`, Morfeusz2) albo jest tym samym słowem;
2. albo pasuje po wspólnym początku, a słownik zna je jako imię lub nazwisko albo go nie zna.

Dopasowanie po wspólnym początku (na słowach złożonych przez `fold_word()`): wspólny początek ma
długość słowa wskazanego bez dwóch ostatnich liter, a nie mniej niż 3 litery, a słowo w tekście
ma po nim najwyżej 4 litery. Zawsze: słowo wskazane ma co najmniej 3 litery, słowo z wielkiej
litery pasuje tylko do słowa z wielkiej litery, a słów w znacznikach reguła nie bierze.

| wskazane   | w tekście   | lemat        | po początku | wynik                             |
|------------|-------------|--------------|-------------|-----------------------------------|
| Dudziak    | Dudziakowi  | wspólny      | tak         | odmiana                           |
| Ewa        | Ewie        | wspólny      | nie         | odmiana                           |
| Iza        | Izabela     | różny        | tak         | odmiana — „Izabela” to imię       |
| Ala        | Alarm       | różny        | tak         | nie — „alarm” to zwykły rzeczownik |
| Lis        | Lista       | różny        | tak         | nie — „lista” to zwykły rzeczownik |
| Sobczakową | Sobczakowej | spoza słow.  | tak         | odmiana                           |

O czym pamiętać przy zmianach:

- Sam lemat gubi zdrobnienie („Iza” obok „Izabela”), a sam początek łapie zwykłe słowa („Alarm”
  obok „Ala”); reguła bierze z obu to, co pewne. Pomiar z 2026-10-19 na odpowiedziach modelu dla
  golden setu: zniszczona wiedza zestawu zmyślonego 2 → 0, bez nowego przecieku.
- Nadal łapie słowo, które słownik zna też jako nazwisko: „Nowego” na początku zdania obok
  „Nowak” (słownik ma nazwisko „Nowy”). Pomyłka jest w stronę zamiany, nie przecieku.
"""

import re

from anonymizer_app.core_service.analyzer_morphology import analyse_word
from anonymizer_app.core_service.finder_markers import marker_spans
from anonymizer_app.core_util.fold import fold_word
from anonymizer_app.core_util.spans import is_inside

# Słowo: ciąg liter, bez cyfr i podkreśleń.
LETTERS = re.compile(r"[^\W\d_]+")

# Słowo wskazane krótsze niż tyle liter nie ma odmian: przy dwóch literach wspólny początek ma
# prawie każde słowo.
MIN_WORD_LETTERS = 3

# Ile ostatnich liter słowa wskazanego może się różnić — miejsce na końcówkę odmiany.
ENDING_LETTERS = 2

# Ile liter słowo w tekście może mieć po wspólnym początku.
MAX_TAIL_LETTERS = 4


def find_word_forms(
    text: str,  # np. "Pan Dudziak dzwonił. Proszę przekazać Dudziakowi…"
    word: str,  # np. "Dudziak"
) -> list[tuple[int, int]]:
    """
    Description:
    Zakresy słów tekstu, które są odmianą wskazanego słowa według reguły z opisu modułu, poza
    znacznikami. Słowo krótsze niż trzy litery nie ma odmian.

    Example args:
        text="Pan Dudziak dzwonił. Proszę przekazać Dudziakowi, że dudziak to ptak."
        word="Dudziak"

    Example result:
        [(4, 11), (38, 48)]
    """
    folded = fold_word(word)

    if len(folded) < MIN_WORD_LETTERS:
        return []

    markers = marker_spans(text)
    lemmas  = analyse_word(word).lemmas
    found   = []

    for match in LETTERS.finditer(text):
        candidate = match.group()

        # --- słowo w znaczniku to dana już zamieniona ---
        if is_inside(match.span(), markers):
            continue

        # --- wielka litera wskazanego słowa jest częścią nazwy: „Lis” to nie „lis” ---
        if word[0].isupper() and not candidate[0].isupper():
            continue

        if _is_form(folded, lemmas, candidate):
            found.append(match.span())

    return found


def _is_form(
    folded: str,             # wskazane słowo złożone, np. "iza"
    lemmas: frozenset[str],  # jego lematy, np. frozenset({"iza"})
    candidate: str,          # słowo z tekstu, np. "Izabela"
) -> bool:
    """
    Description:
    Mówi, czy słowo z tekstu jest odmianą wskazanego: wspólny lemat albo to samo słowo, a gdy
    nie — wspólny początek, ale tylko na słowo, które słownik zna jako imię lub nazwisko albo go
    nie zna.

    Example args:
        folded="iza"
        lemmas=frozenset({"iza"})
        candidate="Izabela"

    Example result:
        True
    """
    folded_candidate = fold_word(candidate)
    analysis         = analyse_word(candidate)

    # --- ten sam lemat albo to samo słowo: odmiana na pewno ---
    if lemmas & analysis.lemmas or folded_candidate == folded:
        return True

    # --- zwykłe słowo ze słownika („Alarm”, „Lista”) nie jest osobą, choć zaczyna się tak samo ---
    if analysis.known and not analysis.proper_name:
        return False

    return is_stem_form(folded, folded_candidate)


def is_stem_form(
    folded:           str,  # wskazane słowo złożone przez fold_word(), np. "doreczenia"
    folded_candidate: str,  # słowo z tekstu złożone przez fold_word(), np. "doreczen"
) -> bool:
    """
    Description:
    Mówi, czy słowo z tekstu pasuje do wskazanego po wspólnym początku: początek ma długość
    wskazanego bez dwóch ostatnich liter, a nie mniej niż 3 litery, a po nim słowo z tekstu ma
    najwyżej 4 litery. Działa w obie strony długości, więc łapie też formę krótszą
    („Doręczeń” przy „Doręczenia”).

    Example args:
        folded="doreczenia"
        folded_candidate="doreczen"

    Example result:
        True
    """
    common = _common_prefix(folded, folded_candidate)
    needed = max(MIN_WORD_LETTERS, len(folded) - ENDING_LETTERS)

    return common >= needed and len(folded_candidate) - common <= MAX_TAIL_LETTERS


def _common_prefix(
    first:  str,  # np. "dudziak"
    second: str,  # np. "dudziakowi"
) -> int:
    """
    Description:
    Długość wspólnego początku dwóch słów.

    Example args:
        first="dudziak"
        second="dudziakowi"

    Example result:
        7
    """
    length = 0

    # Bez `strict`: słowa mają różne długości, a wspólny początek kończy krótsze.
    for left, right in zip(first, second, strict=False):
        if left != right:
            break

        length += 1

    return length
