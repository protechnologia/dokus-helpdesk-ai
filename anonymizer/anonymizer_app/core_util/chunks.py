"""
Description:
Podział długiego tekstu na części, które model przejrzy osobno. Wątek korpusu ma medianę 337
tokenów, ale najdłuższy około 40 tys., czyli więcej niż okno modelu (zmierzone 2026-10-19 na
1825 zgłoszeniach). Model w każdej części tylko wskazuje fragmenty, a kod szuka ich i zamienia
w całym tekście, więc podział niczego nie gubi: osoba wskazana w jednej części znika także
z pozostałych.

Przykład (najwyżej 30 znaków na część):

    przed: „Od: Leszek Dudziak\\nDo: kancelaria\\nProszę o zmianę adresu.”
    po:    [„Od: Leszek Dudziak\\nDo: kancelaria\\n”, „Proszę o zmianę adresu.”]

Kroki:

1. Tekst dzieli się na linie, ze znakiem nowej linii przy każdej.
2. Linie dokłada się do części, dopóki część mieści się w limicie.
3. Linia dłuższa niż limit dzieli się na ostatnim odstępie przed limitem, a bez odstępu — na
   samym limicie.

O czym pamiętać przy zmianach:

- Imię i nazwisko złamane na granicy dwóch części model widzi osobno; każde słowo wskazane
  w jednej części i tak zamienia się w całym tekście.
"""


def split_into_chunks(
    text:      str,  # np. "Od: Leszek Dudziak\nDo: kancelaria\nProszę o zmianę adresu."
    max_chars: int,  # np. 6000
) -> list[str]:
    """
    Description:
    Części tekstu w kolejności, każda najwyżej `max_chars` znaków; złączone dają tekst bez zmian.
    Tekst, który mieści się w limicie, to jedna część.

    Example args:
        text="Od: Leszek Dudziak\\nDo: kancelaria\\nProszę o zmianę adresu."
        max_chars=30

    Example result:
        ["Od: Leszek Dudziak\\nDo: kancelaria\\n", "Proszę o zmianę adresu."]
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""

    for line in _pieces(text, max_chars):
        if current and len(current) + len(line) > max_chars:
            chunks.append(current)
            current = ""

        current += line

    if current:
        chunks.append(current)

    return chunks


def _pieces(
    text:      str,  # np. "Linia pierwsza\nLinia druga"
    max_chars: int,  # np. 6000
) -> list[str]:
    """
    Description:
    Linie tekstu ze znakiem nowej linii przy każdej, a linie dłuższe niż limit — pocięte na
    kawałki, które się w nim mieszczą.

    Example args:
        text="aaa bbb ccc\\nkrótka"
        max_chars=8

    Example result:
        ["aaa bbb ", "ccc\\n", "krótka"]
    """
    pieces: list[str] = []

    for line in text.splitlines(keepends=True):
        while len(line) > max_chars:
            # Na ostatnim odstępie przed limitem, żeby nie przeciąć słowa; bez odstępu na limicie.
            cut = line.rfind(" ", 0, max_chars) + 1 or max_chars
            pieces.append(line[:cut])
            line = line[cut:]

        pieces.append(line)

    return pieces
