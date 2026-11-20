"""
Description:
Usuwa z kolejnych tekstów linie, które w całości powtarzają tekst już widziany: wcześniej
w tym samym tekście, w jednym z poprzednich albo na liście znanych fragmentów. Powtórzeniem
jest ciąg co najmniej `run_words` kolejnych słów; słowo to ciąg liter i cyfr, porównywany bez
wielkości liter, więc interpunkcja, odstępy i łamanie linii nie mają znaczenia, a litery
z ogonkami muszą się zgadzać.

Przykład dla `run_words=5` — dwa teksty, drugi cytuje pierwszy z dopisanym słowem:

    tekst 1:  Od wczoraj nie możemy wysłać pisma.
              Komunikat brzmi: Brak uprawnień do skrzynki.

    tekst 2:  Proszę odnowić uprawnienie.
              > od wczoraj nie możemy wysłać pisma
              > Komunikat nadal brzmi: Brak uprawnień do skrzynki.

    wynik 2:  Proszę odnowić uprawnienie.
              > Komunikat nadal brzmi: Brak uprawnień do skrzynki.

Pierwsza linia cytatu znika, bo każde jej słowo leży w ciągu pięciu słów, który stał już
w tekście 1. Druga zostaje, bo stoi w niej nowe słowo „nadal”: żaden ciąg z nim wcześniej nie
stał.

Kroki (`remove_repeated_lines`):

1. Tekst dzieli się na słowa, każde z miejscem w tekście.
2. Każde okno `run_words` kolejnych słów, które stało już wcześniej albo którego skrót jest na
   liście znanych, oznacza swoje słowa jako powtórzone. Potem okno trafia do widzianych.
3. Linia, w której każde słowo jest powtórzone, znika. Linia bez słów (pusta, sama
   interpunkcja) zostaje.
4. Puste linie po wycięciu zwijają się do jednej, a brzegi tekstu tracą białe znaki.

O czym pamiętać przy zmianach:

- Znika cała linia albo nic. Cięcie po słowach zostawiało strzępy zdań (połowa linii cytatu,
  dwukropek bez etykiety), a model gorzej czyta strzępy niż linię, która została w całości.
- Skrót okna liczy `run_digest()` i tylko ta funkcja: listę znanych skrótów buduje się z niej
  (skrypt słownika), więc inny sposób liczenia po jednej stronie po cichu wyłączyłby listę.
- Zmiana tego, co jest słowem (`WORD`, małe litery), zmienia skróty: listę znanych trzeba wtedy
  zbudować od nowa.
"""

import hashlib
import re
from collections.abc import Collection, Sequence

# Słowo: ciąg liter, cyfr i podkreśleń; wszystko inne (interpunkcja, odstępy, nowe linie)
# tylko je rozdziela.
WORD = re.compile(r"\w+")

# Trzy i więcej nowych linii pod rząd, także z białymi znakami między nimi: zostaje jedna pusta
# linia.
BLANK_LINES = re.compile(r"\n\s*\n\s*\n+")

# Długość skrótu okna w bajtach: 8 bajtów to 16 znaków szesnastkowych, a przy kilkuset wpisach
# na liście przypadkowa zgodność dwóch różnych okien jest praktycznie wykluczona.
DIGEST_BYTES = 8


def words_of(text: str) -> list[str]:   # np. "Komunikat: „Brak uprawnień”."
    """
    Description:
    Dzieli tekst na słowa i zapisuje je małymi literami, w kolejności z tekstu.

    Example args:
        text="Komunikat: „Brak uprawnień”."

    Example result:
        ["komunikat", "brak", "uprawnień"]
    """
    words = [match.group().lower() for match in WORD.finditer(text)]

    return words


def run_digest(words: Sequence[str]) -> str:   # np. ["treść", "tej", "wiadomości", …]
    """
    Description:
    Liczy skrót ciągu słów: BLAKE2b z 8 bajtami wyniku, ze słów złączonych pojedynczą spacją.
    Tak zapisuje się znane fragmenty, żeby lista nie trzymała czytelnego tekstu.

    Example args:
        words=["treść", "tej", "wiadomości", "zawiera", …]

    Example result:
        "5be28f491fc44ae7"
    """
    joined = " ".join(words).encode("utf-8")

    return hashlib.blake2b(joined, digest_size=DIGEST_BYTES).hexdigest()


def run_digests(
    text:      str,  # np. "Treść tej wiadomości zawiera informacje przeznaczone…"
    run_words: int,  # np. 12 — długość okna w słowach
) -> set[str]:
    """
    Description:
    Oddaje skróty wszystkich okien `run_words` kolejnych słów tekstu, bez powtórzeń. Z nich
    skrypt słownika liczy, w ilu tekstach stoi każdy fragment.

    Example args:
        text="Treść tej wiadomości zawiera informacje przeznaczone tylko dla adresata. Jeżeli…"
        run_words=12

    Example result:
        {"5be28f491fc44ae7", "0d3c…", …}
    """
    words   = words_of(text)
    digests = {
        run_digest(words[start:start + run_words])
        for start in range(len(words) - run_words + 1)
    }

    return digests


def remove_repeated_lines(
    texts:     Sequence[str],    # np. ["Nie możemy wysłać…", "Proszę odnowić…\n> nie możemy…"]
    run_words: int,              # np. 12 — od ilu kolejnych słów liczy się powtórzenie
    known:     Collection[str],  # np. {"5be28f491fc44ae7"} — skróty okien usuwanych zawsze
) -> list[str]:
    """
    Description:
    Oddaje teksty w tej samej kolejności, każdy bez linii, które w całości leżą w powtórzonych
    oknach: takich, które stały już wcześniej (w tym tekście albo w poprzednich), albo takich,
    których skrót jest na liście znanych. Linia znanego fragmentu znika także przy pierwszym
    wystąpieniu.

    Example args:
        texts=["Nie możemy wysłać pisma.", "Proszę odnowić.\n> nie możemy wysłać pisma"]
        run_words=5
        known=set()

    Example result:
        ["Nie możemy wysłać pisma.", "Proszę odnowić."]
    """
    seen:    set[tuple[str, ...]] = set()
    cleaned: list[str]            = []

    for text in texts:
        matches  = list(WORD.finditer(text))
        words    = [match.group().lower() for match in matches]
        repeated = [False] * len(words)

        # --- oznaczenie słów w powtórzonych oknach ---
        for start in range(len(words) - run_words + 1):
            window = tuple(words[start:start + run_words])

            if window in seen or run_digest(window) in known:
                repeated[start:start + run_words] = [True] * run_words

            # Okno trafia do widzianych po sprawdzeniu, więc liczy się tylko wcześniejsze
            # wystąpienie, także w tym samym tekście (druga kopia maila w jednym polu).
            seen.add(window)

        cleaned.append(_without_repeated_lines(text, matches, repeated))

    return cleaned


def _without_repeated_lines(
    text:     str,                  # np. "Proszę odnowić.\n> od wczoraj nie możemy wysłać pisma"
    matches:  Sequence[re.Match],   # słowa tekstu z miejscami, w kolejności
    repeated: Sequence[bool],       # np. [False, False, True, True, …] — słowo po słowie
) -> str:
    """
    Description:
    Składa tekst z linii, które zostają: bez słów albo z choć jednym słowem spoza powtórzeń.
    Puste linie zwija do jednej i zdejmuje białe znaki z brzegów.

    Example args:
        text="Proszę odnowić.\\n> od wczoraj nie możemy wysłać pisma"
        matches=[<re.Match 'Proszę'>, <re.Match 'odnowić'>, <re.Match 'od'>, …]
        repeated=[False, False, True, True, True, True, True, True]

    Example result:
        "Proszę odnowić."
    """
    kept:  list[str] = []
    index: int       = 0
    start: int       = 0

    for line in text.split("\n"):
        end = start + len(line)

        # --- słowa tej linii: od bieżącego miejsca do jej końca ---
        line_words = []
        while index < len(matches) and matches[index].start() < end:
            line_words.append(repeated[index])
            index += 1

        # Linia bez słów zostaje: nie ma w niej czego powtórzyć, a pusta linia dzieli akapity.
        if not (line_words and all(line_words)):
            kept.append(line)

        # Znak nowej linii, którego `split()` nie oddaje.
        start = end + 1

    joined = BLANK_LINES.sub("\n\n", "\n".join(kept)).strip()

    return joined
