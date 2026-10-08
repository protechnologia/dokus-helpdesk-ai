"""
Description:
Testy jednostkowe zmian, które skrypt paczki kodu (`scripts/build_code_package.py`) wprowadza
w treści plików: rozkodowania polskich liter zapisanych sekwencjami i zamiany końców linii.

| funkcja                 | czego pilnują testy                                              |
|-------------------------|------------------------------------------------------------------|
| `decode_polish_escapes` | każda polska litera się rozkodowuje, inne sekwencje zostają      |
| `decode_polish_escapes` | parzysta liczba ukośników to nie sekwencja; linie zostają        |
| `transform`             | sekwencje tylko w plikach JS, końce linii CRLF w każdym pliku    |

O czym pamiętać przy zmianach:

- Sekwencję litery buduje `_escape()`, z ukośnika i kodu znaku. Dzięki temu w tym pliku nie ma
  ani jednej sekwencji zapisanej wprost, którą edytor albo narzędzie mogłyby po drodze zamienić
  na literę — test porównywałby wtedy literę z literą.
- Lista polskich liter jest tu wpisana osobno, a nie brana ze skryptu: inaczej litera usunięta
  z tabeli skryptu zniknęłaby też z testu.
"""

import pytest
from build_code_package import decode_polish_escapes, transform

BACKSLASH      = "\\"
POLISH_LETTERS = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"


def _escape(
    letter: str,  # np. "ł"
) -> str:
    """
    Description:
    Zapisuje literę sekwencją, tak jak stoi ona w plikach JS aplikacji: ukośnik, `u` i cztery
    cyfry szesnastkowe kodu znaku, małymi literami.

    Example args:
        letter="ł"

    Example result:
        ukośnik i „u0142" (sześć znaków)
    """
    return f"{BACKSLASH}u{ord(letter):04x}"


@pytest.mark.parametrize("letter", POLISH_LETTERS)
def test_every_polish_letter_is_decoded(letter: str) -> None:
    """Sprawdza, czy sekwencja każdej z osiemnastu polskich liter zamienia się na samą literę,
    także gdy cyfry szesnastkowe są zapisane wielkimi literami.

    Wyłapuje literę, której brakuje w tabeli skryptu: dosłowne szukanie komunikatu z tą literą
    nie znalazłoby linii, w której została sekwencja."""
    lower = _escape(letter)
    upper = lower[:2] + lower[2:].upper()

    assert decode_polish_escapes(f"msg: '{lower}'") == (f"msg: '{letter}'", 1)
    assert decode_polish_escapes(f"msg: '{upper}'") == (f"msg: '{letter}'", 1)


@pytest.mark.parametrize(
    "code",
    [
        "0022",  # cudzysłów: rozkodowany zamknąłby napis w połowie
        "000a",  # znak nowej linii: rozkodowany przesunąłby numery linii
        "2028",  # separator linii
        "00e9",  # litera spoza polskiego alfabetu
    ],
)
def test_an_escape_that_is_not_a_polish_letter_stays(code: str) -> None:
    """Sprawdza, czy sekwencja znaku, który nie jest polską literą, zostaje w tekście bez zmian
    i nie jest liczona jako zmieniona linia.

    Wyłapuje rozkodowanie wszystkich sekwencji naraz: cudzysłów zepsułby składnię pliku, a znak
    nowej linii przesunąłby numery linii względem kodu aplikacji."""
    text = f"msg: 'a{BACKSLASH}u{code}b'"

    assert decode_polish_escapes(text) == (text, 0)


def test_an_escaped_backslash_before_u_is_not_a_sequence() -> None:
    """Sprawdza, czy zapis z dwoma ukośnikami przed `u` zostaje bez zmian, a z trzema zamienia
    się na dwa ukośniki i literę.

    Wyłapuje rozkodowanie, które nie liczy ukośników: przy dwóch kod widzi ukośnik i zwykły
    tekst „u0142", więc litera wstawiona w to miejsce zmieniłaby to, co program wypisuje."""
    two_slashes   = f"{BACKSLASH * 2}u0142"
    three_slashes = f"{BACKSLASH * 3}u0142"

    assert decode_polish_escapes(two_slashes)   == (two_slashes, 0)
    assert decode_polish_escapes(three_slashes) == (f"{BACKSLASH * 2}ł", 1)


def test_decoding_keeps_every_line_in_its_place() -> None:
    """Sprawdza, czy po rozkodowaniu tekst ma te same linie w tej samej kolejności, linie bez
    sekwencji są nietknięte, a licznik podaje liczbę zmienionych linii, nie liczbę sekwencji.

    Wyłapuje rozkodowanie, które przesuwa albo źle liczy linie: numer linii z paczki przestałby
    wskazywać to samo miejsce co w kodzie aplikacji, a metryczka podawałaby inną liczbę zmian,
    niż skrypt wprowadził."""
    text = "\n".join([
        "var a = 1;",
        f"var b = 'Nie uda{_escape('ł')}o si{_escape('ę')}';",  # dwie sekwencje w jednej linii
        "",
        f"var c = 'B{_escape('ł')}{_escape('ą')}d';",
        "var d = 2;",
    ])

    decoded, changed_lines = decode_polish_escapes(text)

    assert decoded.split("\n") == [
        "var a = 1;",
        "var b = 'Nie udało się';",
        "",
        "var c = 'Błąd';",
        "var d = 2;",
    ]
    assert changed_lines == 2


@pytest.mark.parametrize(
    "path",
    [
        "src/web/js/_global/bledy.js",  # plik JS
        "src/web/js/_global/BLEDY.JS",  # rozszerzenie wielkimi literami
    ],
)
def test_escapes_in_js_files_are_decoded(path: str) -> None:
    """Sprawdza, czy w pliku JS, także z rozszerzeniem zapisanym wielkimi literami, sekwencja
    polskiej litery jest rozkodowana i policzona jako jedna zmieniona linia.

    Wyłapuje poprawianie treści, które pomija pliki JS: komunikaty z ekranu zostałyby w paczce
    sekwencjami i dosłowne szukanie by ich nie znalazło."""
    text = f"msg: 'Nie uda{_escape('ł')}o'\n"

    assert transform(path, text) == ("msg: 'Nie udało'\n", False, 1)


@pytest.mark.parametrize(
    "path",
    [
        "src/lib/Urzad/Komunikaty.php",             # PHP
        "src/lib/Urzad/Poczta/powiadomienie.twig",  # szablon Twig
        "src/config/doctrine/schema_pisma.yml",     # plik wskazany wprost
    ],
)
def test_escapes_outside_js_files_stay(path: str) -> None:
    """Sprawdza, czy w pliku innym niż JS sekwencja polskiej litery zostaje w tekście bez zmian.

    Wyłapuje rozkodowanie we wszystkich plikach: w PHP w pojedynczych cudzysłowach ten zapis
    jest dosłowny, więc paczka pokazywałaby modelowi inny tekst, niż aplikacja wypisuje."""
    text = f"$msg = 'Nie uda{_escape('ł')}o';\n"

    assert transform(path, text) == (text, False, 0)


@pytest.mark.parametrize(
    "path",
    [
        "src/lib/Urzad/Komunikaty.php",             # PHP
        "src/web/js/_global/bledy.js",              # JS
        "src/lib/Urzad/Poczta/powiadomienie.twig",  # szablon Twig
    ],
)
def test_crlf_line_endings_become_lf_in_every_file(path: str) -> None:
    """Sprawdza, czy końce linii CRLF zamieniają się na LF w pliku każdego rodzaju, a zmiana jest
    odnotowana.

    Wyłapuje CRLF zostawiony w paczce: czytnik paczki dzieli linie samym znakiem nowej linii,
    więc każda linia oddana modelowi kończyłaby się znakiem powrotu karetki."""
    assert transform(path, "a\r\nb\r\n") == ("a\nb\n", True, 0)


def test_a_file_with_lf_line_endings_is_reported_as_unchanged() -> None:
    """Sprawdza, czy plik, który ma już końce linii LF, wraca bez zmian i bez odnotowanej zamiany.

    Wyłapuje licznik, który zalicza do poprawionych każdy plik: metryczka mówiłaby, że skrypt
    zmienił końce linii tam, gdzie niczego nie ruszył."""
    assert transform("src/lib/Urzad/Komunikaty.php", "a\nb\n") == ("a\nb\n", False, 0)
