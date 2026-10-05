import re

import pytest

from app.core_service.builder_doc_embedding_text import build_fragment_text, split_into_fragments

# Cięcie treści sekcji na fragmenty: czyste funkcje, bez plików i usług. Treści są zmyślone.

HEADING = "### Kancelaria"


def _paragraph(
    length: int,       # np. 600
    word:   str = "a",  # z czego składa się akapit
) -> str:
    """
    Description:
    Buduje akapit o dokładnie podanej długości: jedna linia jednoliterowych słów rozdzielonych
    spacjami. Przy długości parzystej ostatnie słowo ma dwie litery, żeby akapit nie kończył się
    spacją.

    Example args:
        length=6
        word="a"

    Example result:
        "a a aa"
    """
    text = (f"{word} " * length)[:length]

    return f"{text[:-1]}{word}" if text.endswith(" ") else text


def _squash(
    text: str,  # np. "Wstęp.\n\n### Kancelaria"
) -> str:
    """
    Description:
    Sprowadza każdy ciąg białych znaków do jednej spacji — do porównania treści bez względu na
    to, gdzie wypadły granice fragmentów.

    Example args:
        text="Wstęp.\\n\\n### Kancelaria"

    Example result:
        "Wstęp. ### Kancelaria"
    """
    return re.sub(r"\s+", " ", text).strip()


# --- całe akapity -------------------------------------------------------------------------

def test_a_short_body_is_one_fragment() -> None:
    """Sprawdza, czy treść krótsza niż limit zostaje jednym fragmentem: dwa krótkie akapity przy
    limicie 1500 znaków wracają razem, bez zmian poza zdjętym znakiem końca linii na samym końcu.

    Wyłapuje cięcie, które dzieli albo przerabia treść mieszczącą się w limicie: krótka sekcja
    dostałaby wtedy kilka wektorów z urywków zamiast jednego z całości."""
    assert split_into_fragments("Pierwszy akapit.\n\nDrugi akapit.\n", 1500) == [
        "Pierwszy akapit.\n\nDrugi akapit."
    ]


@pytest.mark.parametrize("body", ["", "   ", "\n\n\n"])
def test_an_empty_body_gives_no_fragments(body: str) -> None:
    """Sprawdza, czy pusta treść nie daje żadnego fragmentu. Trzy przypadki: brak znaków, same
    spacje i same puste linie.

    Wyłapuje jeden pusty fragment oddany zamiast pustej listy: pusta sekcja dostałaby wtedy
    w indeksie punkt, za którym nie stoi żadna treść."""
    assert split_into_fragments(body, 1500) == []


def test_paragraphs_are_packed_up_to_the_limit() -> None:
    """Sprawdza, czy kolejne akapity trafiają do jednego fragmentu, dopóki mieszczą się w limicie:
    przy akapitach po 600, 700 i 500 znaków i limicie 1500 dwa pierwsze są razem, a trzeci osobno.

    Wyłapuje dwie usterki: fragment dłuższy niż limit oraz osobny fragment na każdy akapit, przez
    który wektory powstawałyby z urywków mniejszych, niż limit pozwala."""
    first, second, third = _paragraph(600, "a"), _paragraph(700, "b"), _paragraph(500, "c")

    fragments = split_into_fragments(f"{first}\n\n{second}\n\n{third}", 1500)

    assert fragments == [f"{first}\n\n{second}", third]


def test_a_paragraph_that_fits_is_never_cut() -> None:
    """Sprawdza, czy akapit, który sam mieści się w limicie, nie jest cięty: z dwóch akapitów po
    900 znaków przy limicie 1500 drugi przechodzi w całości do następnego fragmentu.

    Wyłapuje dopełnianie fragmentu początkiem następnego akapitu: akapit zostałby rozerwany tam,
    gdzie akurat wypadł limit, a jego dwie części trafiłyby do różnych wektorów."""
    first, second = _paragraph(900, "a"), _paragraph(900, "b")

    assert split_into_fragments(f"{first}\n\n{second}", 1500) == [first, second]


def test_a_blank_line_with_spaces_separates_paragraphs() -> None:
    """Sprawdza, czy pusta linia, w której zostały spacje, i kilka pustych linii pod rząd liczą się
    jako jedna granica akapitu: z takiej treści wychodzą dokładnie dwa fragmenty, po jednym na
    akapit.

    Wyłapuje cięcie, które takiej granicy nie rozpoznaje: akapity zlałyby się w jeden fragment albo
    zostałyby w nich zbędne puste linie i spacje."""
    fragments = split_into_fragments("Pierwszy.\n   \n\n\nDrugi.", 9)

    assert fragments == ["Pierwszy.", "Drugi."]


def test_spaces_before_a_blank_line_do_not_stay_in_the_paragraph() -> None:
    """Sprawdza, czy spacje z końca akapitu, stojące przed pustą linią, nie trafiają do fragmentu,
    a wcięcie następnego akapitu zostaje na miejscu.

    Wyłapuje dwie usterki: zbędne spacje, które zajmują miejsce w limicie fragmentu, oraz zdjęte
    wcięcie, po którym wcięty blok, na przykład kod, przestaje się wyróżniać."""
    fragments = split_into_fragments("Pierwszy.   \n\n    wcięty kod", 14)

    assert fragments == ["Pierwszy.", "    wcięty kod"]


# --- akapit dłuższy niż limit -------------------------------------------------------------

def test_a_long_paragraph_is_cut_between_lines() -> None:
    """Sprawdza, czy akapit dłuższy niż limit jest cięty między liniami: lista sześciu pozycji przy
    limicie 70 znaków daje trzy fragmenty po dwie całe pozycje.

    Wyłapuje cięcie w środku pozycji listy: kod uprawnienia trafiłby do jednego fragmentu, a jego
    opis do drugiego, więc żaden wektor nie niósłby całej pozycji."""
    lines = [f"- `KOD_{number}` — opis uprawnienia" for number in range(6)]

    fragments = split_into_fragments("\n".join(lines), 70)

    assert fragments == ["\n".join(lines[0:2]), "\n".join(lines[2:4]), "\n".join(lines[4:6])]


def test_a_long_line_is_cut_between_sentences() -> None:
    """Sprawdza, czy akapit prozy zapisany w jednej linii i dłuższy niż limit jest cięty na końcach
    zdań: trzy zdania, zakończone kropką, pytajnikiem i wykrzyknikiem, przy limicie 40 znaków dają
    trzy fragmenty po jednym całym zdaniu.

    Wyłapuje cięcie w środku zdania oraz koniec zdania rozpoznawany tylko po kropce: zdanie urwane
    w połowie nie mówi już tego, co mówiło w instrukcji."""
    first  = "Uprawnienie nadaje administrator."
    second = "Czy działa od razu?"
    third  = "Nie, dopiero po ponownym zalogowaniu!"

    fragments = split_into_fragments(f"{first} {second} {third}", 40)

    assert fragments == [first, second, third]


def test_sentences_are_packed_up_to_the_limit() -> None:
    """Sprawdza, czy zdania pociętego akapitu są łączone z powrotem do limitu: z trzech zdań przy
    limicie 60 znaków dwa pierwsze są razem, a trzecie osobno, bo cięcie wypada na ostatnim końcu
    zdania, który się mieści.

    Wyłapuje osobny fragment na każde zdanie bez względu na limit: długi akapit rozpadłby się na
    fragmenty zbyt krótkie, żeby wektor oddawał, o czym jest mowa."""
    first  = "Uprawnienie nadaje administrator."
    second = "Czy działa od razu?"
    third  = "Nie, dopiero po ponownym zalogowaniu!"

    fragments = split_into_fragments(f"{first} {second} {third}", 60)

    assert fragments == [f"{first} {second}", third]


def test_a_number_with_a_dot_is_not_a_sentence_end() -> None:
    """Sprawdza, czy kropka, po której nie ma odstępu, nie jest brana za koniec zdania: w tekście
    z wydaniem 4.12 i limitem 3.5 MB cięcie wypada dopiero po całym zdaniu.

    Wyłapuje traktowanie każdej kropki jak końca zdania: numer wydania albo wartość limitu zostałyby
    rozerwane na dwie części."""
    fragments = split_into_fragments("Od wydania 4.12 limit wynosi 3.5 MB. Dalej bez zmian.", 40)

    assert fragments == ["Od wydania 4.12 limit wynosi 3.5 MB.", "Dalej bez zmian."]


def test_a_long_sentence_is_cut_between_words() -> None:
    """Sprawdza, czy zdanie dłuższe niż limit jest cięte na spacjach: sześć słów przy limicie
    14 znaków daje trzy fragmenty i żadne słowo nie jest rozerwane.

    Wyłapuje cięcie co limit znaków bez patrzenia na słowa: we fragmentach zostałyby połówki słów,
    z których nie da się odczytać treści."""
    fragments = split_into_fragments("jeden dwa trzy cztery pięć sześć", 14)

    assert fragments == ["jeden dwa trzy", "cztery pięć", "sześć"]


def test_a_word_longer_than_the_limit_is_cut_by_characters() -> None:
    """Sprawdza, czy ciąg bez spacji dłuższy niż limit jest cięty co limit znaków: dziesięć liter
    przy limicie 4 daje fragmenty po 4, 4 i 2 znaki.

    Wyłapuje dwie usterki: fragment dłuższy niż limit, gdy nie ma już spacji, na której można ciąć,
    oraz zgubioną końcówkę takiego ciągu."""
    assert split_into_fragments("abcdefghij", 4) == ["abcd", "efgh", "ij"]


def test_the_tail_of_a_cut_paragraph_joins_the_next_one() -> None:
    """Sprawdza, czy końcówka pociętego akapitu łączy się z następnym krótkim akapitem w jeden
    fragment: przy limicie 14 znaków ostatnie słowo akapitu „jeden dwa trzy cztery" stoi razem
    z akapitem „koniec".

    Wyłapuje zamykanie fragmentu po każdym pociętym akapicie: zostawałyby fragmenty z jednego słowa,
    zbyt krótkie, żeby ich wektor cokolwiek znaczył."""
    fragments = split_into_fragments("jeden dwa trzy cztery\n\nkoniec", 14)

    assert fragments == ["jeden dwa trzy", "cztery\n\nkoniec"]


# --- nagłówki -----------------------------------------------------------------------------

def test_a_heading_moves_on_with_its_block() -> None:
    """Sprawdza, czy nagłówek nie zostaje na końcu fragmentu: nagłówek „### Kancelaria", który
    zmieściłby się jeszcze za wstępem, stoi w następnym fragmencie, przed blokiem, który opisuje.

    Wyłapuje rozdzielenie nagłówka i jego bloku: nagłówek bez treści nic nie mówi, a blok bez
    nagłówka traci temat."""
    intro, block = _paragraph(60, "a"), _paragraph(100, "b")

    fragments = split_into_fragments(f"{intro}\n\n{HEADING}\n\n{block}", 120)

    assert fragments == [intro, f"{HEADING}\n\n{block}"]


def test_a_moved_heading_may_exceed_the_limit_by_its_own_length() -> None:
    """Sprawdza, czy fragment zaczynający się od przeniesionego nagłówka może przekroczyć limit
    tylko o ten nagłówek: przy limicie 120 znaków i bloku na 120 znaków drugi fragment ma długość
    nagłówka, pustej linii (dwa znaki) i bloku.

    Wyłapuje zmianę tej reguły w którąkolwiek stronę: nagłówek odcięty od bloku, żeby zmieścić się
    w limicie, albo blok pocięty, choć sam się w nim mieści."""
    intro, block = _paragraph(60, "a"), _paragraph(120, "b")

    fragments = split_into_fragments(f"{intro}\n\n{HEADING}\n\n{block}", 120)

    assert len(fragments[1]) == len(HEADING) + 2 + 120


def test_a_heading_at_the_very_end_stays() -> None:
    """Sprawdza, czy nagłówek, po którym w treści nic już nie ma, zostaje w ostatnim fragmencie.

    Wyłapuje nagłówek zgubiony przy przenoszeniu: reguła, która odkłada nagłówek do następnego
    fragmentu, nie może go skasować, gdy następnego fragmentu nie ma."""
    assert split_into_fragments(f"Wstęp do wykazu.\n\n{HEADING}", 1500) == [
        f"Wstęp do wykazu.\n\n{HEADING}"
    ]


# --- własności całości --------------------------------------------------------------------

@pytest.mark.parametrize("max_chars", [1, 7, 40, 120, 1500])
def test_no_text_is_lost(max_chars: int) -> None:
    """Sprawdza, czy cięcie nie gubi treści: przy pięciu limitach, od 1 do 1500 znaków, fragmenty
    sklejone z powrotem niosą te same znaki co treść, w tej samej kolejności. Porównanie pomija
    białe znaki, bo przy limicie mniejszym niż słowo cięcie wypada w jego środku.

    Wyłapuje fragment zgubiony, powtórzony albo przestawiony: część sekcji nie miałaby wtedy wektora
    i wyszukiwanie po znaczeniu nigdy by jej nie znalazło."""
    body = (
        "Kody uprawnień nadaje się w Ustawienia → Uprawnienia.\n\n"
        f"{HEADING}\n\n"
        "- `KANC_PODGLAD` — przeglądanie korespondencji (Referent).\n"
        "- `KANC_EDYCJA` — edycja korespondencji (Kancelista).\n\n"
        "Uprawnienie spoza profilu nadaje się rolą."
    )

    fragments = split_into_fragments(body, max_chars)

    # Bez białych znaków: przy limicie mniejszym niż słowo cięcie wypada w jego środku.
    assert re.sub(r"\s", "", "".join(fragments)) == re.sub(r"\s", "", body)


@pytest.mark.parametrize("max_chars", [7, 40, 120])
def test_without_headings_no_fragment_exceeds_the_limit(max_chars: int) -> None:
    """Sprawdza, czy w treści bez nagłówków żaden fragment nie przekracza limitu i czy fragmenty
    złożone z powrotem dają tę samą treść. Trzy limity, 7, 40 i 120 znaków, na pięciu akapitach od
    15 do 200 znaków.

    Wyłapuje fragment dłuższy niż limit albo treść zgubioną przy cięciu: jedynym dopuszczonym
    wyjątkiem od limitu jest przeniesiony nagłówek, a tu nagłówków nie ma."""
    body = "\n\n".join(_paragraph(length, "a") for length in (30, 90, 200, 15, 61))

    fragments = split_into_fragments(body, max_chars)

    assert max(len(fragment) for fragment in fragments) <= max_chars
    assert _squash(" ".join(fragments))                 == _squash(body)


# --- tekst do embeddingu ------------------------------------------------------------------

def test_fragment_text_starts_with_the_section_title() -> None:
    """Sprawdza, czy tekst, z którego embedder liczy wektor fragmentu, ma tytuł sekcji w pierwszej
    linii, a pod nim fragment bez zmian.

    Wyłapuje tekst bez tytułu albo ze zmienionym fragmentem: wycinek ze środka długiej sekcji sam
    nie mówi, czego dotyczy, więc bez tytułu zapytanie o temat sekcji mogłoby w niego nie trafić."""
    text = build_fragment_text("Wykaz uprawnień", "- `PIECZEC_UZYCIE` — opatrywanie pieczęcią.")

    assert text == "Wykaz uprawnień\n- `PIECZEC_UZYCIE` — opatrywanie pieczęcią."
