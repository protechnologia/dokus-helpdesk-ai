import unicodedata

# Litery, których rozkład Unicode nie zdejmuje do litery bez znaku. Bez tego „Michał” i „Michal”
# nie byłyby tym samym słowem, a model podaje czasem fragment bez polskich znaków.
EXTRA_LETTERS = str.maketrans({
    "ł": "l",
    "Ł": "l",
})


def fold_word(
    word: str,  # np. "Wiśniewskiej"
) -> str:
    """
    Description:
    Zapisuje słowo do porównań: małe litery, bez polskich znaków (także „ł”). Ta sama reguła co
    w ocenie golden setu, żeby silnik i ocena uważały za to samo słowo te same zapisy.

    Example args:
        word="Wiśniewskiej"

    Example result:
        "wisniewskiej"
    """
    folded  = word.casefold().translate(EXTRA_LETTERS)
    letters = unicodedata.normalize("NFKD", folded)

    return "".join(char for char in letters if not unicodedata.combining(char))


def fold_text(
    text: str,  # np. "na Brzozowej 12 w Sulejowie"
) -> str:
    """
    Description:
    Składa tekst znak po znaku, tak że każda pozycja w wyniku odpowiada tej samej pozycji
    w tekście. Wyrażenie dopasowane do złożonego tekstu wskazuje więc zakres w oryginale. Znak,
    który składa się do więcej niż jednego („ß” → „ss”), zostaje tylko zmniejszony.

    Example args:
        text="na Brzozowej 12 w Sulejowie"

    Example result:
        "na brzozowej 12 w sulejowie"
    """
    chars = []

    for char in text:
        folded = fold_word(char)
        chars.append(folded if len(folded) == 1 else char.lower())

    return "".join(chars)
