import re

import pytest

from app.core_service.builder_doc_fragments import build_fragment_text, split_into_fragments

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
    """Treść krótsza niż limit → jeden fragment, bez zmian poza obcięciem brzegów."""
    assert split_into_fragments("Pierwszy akapit.\n\nDrugi akapit.\n", 1500) == [
        "Pierwszy akapit.\n\nDrugi akapit."
    ]


@pytest.mark.parametrize("body", ["", "   ", "\n\n\n"])
def test_an_empty_body_gives_no_fragments(body: str) -> None:
    """Pusta treść → żadnego fragmentu, a nie jeden pusty."""
    assert split_into_fragments(body, 1500) == []


def test_paragraphs_are_packed_up_to_the_limit() -> None:
    """Akapity 600, 700 i 500 znaków przy limicie 1500 → dwa pierwsze razem, trzeci osobno."""
    first, second, third = _paragraph(600, "a"), _paragraph(700, "b"), _paragraph(500, "c")

    fragments = split_into_fragments(f"{first}\n\n{second}\n\n{third}", 1500)

    assert fragments == [f"{first}\n\n{second}", third]


def test_a_paragraph_that_fits_is_never_cut() -> None:
    """Granica limitu wypada w środku akapitu, który sam się mieści → akapit przechodzi do
    następnego fragmentu w całości."""
    first, second = _paragraph(900, "a"), _paragraph(900, "b")

    assert split_into_fragments(f"{first}\n\n{second}", 1500) == [first, second]


def test_a_blank_line_with_spaces_separates_paragraphs() -> None:
    """Pusta linia ze spacjami i kilka pustych linii pod rząd → nadal jedna granica akapitu."""
    fragments = split_into_fragments("Pierwszy.\n   \n\n\nDrugi.", 9)

    assert fragments == ["Pierwszy.", "Drugi."]


def test_spaces_before_a_blank_line_do_not_stay_in_the_paragraph() -> None:
    """Spacje na końcu akapitu przed pustą linią → nie trafiają do fragmentu, a wcięcie
    następnego akapitu zostaje."""
    fragments = split_into_fragments("Pierwszy.   \n\n    wcięty kod", 14)

    assert fragments == ["Pierwszy.", "    wcięty kod"]


# --- akapit dłuższy niż limit -------------------------------------------------------------

def test_a_long_paragraph_is_cut_between_lines() -> None:
    """Lista dłuższa niż limit → cięta między pozycjami, żadna pozycja nie jest rozerwana."""
    lines = [f"- `KOD_{number}` — opis uprawnienia" for number in range(6)]

    fragments = split_into_fragments("\n".join(lines), 70)

    assert fragments == ["\n".join(lines[0:2]), "\n".join(lines[2:4]), "\n".join(lines[4:6])]


def test_a_long_line_is_cut_between_words() -> None:
    """Linia dłuższa niż limit → cięta na spacjach, żadne słowo nie jest rozerwane."""
    fragments = split_into_fragments("jeden dwa trzy cztery pięć sześć", 14)

    assert fragments == ["jeden dwa trzy", "cztery pięć", "sześć"]


def test_a_word_longer_than_the_limit_is_cut_by_characters() -> None:
    """„Słowo" dłuższe niż limit → cięte co limit znaków: nic innego nie zostało."""
    assert split_into_fragments("abcdefghij", 4) == ["abcd", "efgh", "ij"]


def test_the_tail_of_a_cut_paragraph_joins_the_next_one() -> None:
    """Końcówka pociętego akapitu i następny krótki akapit → jeden fragment."""
    fragments = split_into_fragments("jeden dwa trzy cztery\n\nkoniec", 14)

    assert fragments == ["jeden dwa trzy", "cztery\n\nkoniec"]


# --- nagłówki -----------------------------------------------------------------------------

def test_a_heading_moves_on_with_its_block() -> None:
    """Nagłówek, który zmieściłby się na końcu fragmentu → stoi w następnym, przed swoim
    blokiem."""
    intro, block = _paragraph(60, "a"), _paragraph(100, "b")

    fragments = split_into_fragments(f"{intro}\n\n{HEADING}\n\n{block}", 120)

    assert fragments == [intro, f"{HEADING}\n\n{block}"]


def test_a_moved_heading_may_exceed_the_limit_by_its_own_length() -> None:
    """Fragment zaczynający się od przeniesionego nagłówka → najwyżej limit plus nagłówek."""
    intro, block = _paragraph(60, "a"), _paragraph(120, "b")

    fragments = split_into_fragments(f"{intro}\n\n{HEADING}\n\n{block}", 120)

    assert len(fragments[1]) == len(HEADING) + 2 + 120


def test_a_heading_at_the_very_end_stays() -> None:
    """Nagłówek, po którym nic już nie ma → zostaje w ostatnim fragmencie, nie ginie."""
    assert split_into_fragments(f"Wstęp do wykazu.\n\n{HEADING}", 1500) == [
        f"Wstęp do wykazu.\n\n{HEADING}"
    ]


# --- własności całości --------------------------------------------------------------------

@pytest.mark.parametrize("max_chars", [1, 7, 40, 120, 1500])
def test_no_text_is_lost(max_chars: int) -> None:
    """Dowolny limit → fragmenty sklejone z powrotem niosą całą treść, w tej samej kolejności."""
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
    """Treść bez nagłówków → żaden fragment nie przekracza limitu."""
    body = "\n\n".join(_paragraph(length, "a") for length in (30, 90, 200, 15, 61))

    fragments = split_into_fragments(body, max_chars)

    assert max(len(fragment) for fragment in fragments) <= max_chars
    assert _squash(" ".join(fragments))                 == _squash(body)


# --- tekst do embeddingu ------------------------------------------------------------------

def test_fragment_text_starts_with_the_section_title() -> None:
    """Tytuł sekcji i fragment → tytuł w pierwszej linii, pod nim fragment bez zmian: wycinek
    ze środka długiej sekcji sam nie mówi, czego dotyczy."""
    text = build_fragment_text("Wykaz uprawnień", "- `PIECZEC_UZYCIE` — opatrywanie pieczęcią.")

    assert text == "Wykaz uprawnień\n- `PIECZEC_UZYCIE` — opatrywanie pieczęcią."
