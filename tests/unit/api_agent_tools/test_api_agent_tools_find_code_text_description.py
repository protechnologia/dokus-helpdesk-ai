from app.agent_tools.code.find_code_text import (
    MAX_LINES_PER_SEARCH,
    MAX_TEXT_CHARS,
    MIN_LONGEST_WORD_CHARS,
    FakeFindCodeTextTool,
    FindCodeTextResult,
    MatchedLine,
)
from app.agent_tools.code.find_code_text.base import CUT_MARK

# Opis `find_code_text` dla modelu podaje liczby, które kod trzyma w stałych. Układ opisu sprawdza
# test kontraktu narzędzi; tu pilnujemy tylko tego, żeby opis i kod mówiły to samo.

DESCRIPTION = FakeFindCodeTextTool().description


def test_the_description_names_the_result_limit_of_the_code() -> None:
    """Sprawdza, czy opis narzędzia podaje modelowi limit długości wyniku równy stałej
    `MAX_LINES_PER_SEARCH`, w zdaniu „najwyżej … linii".

    Wyłapuje zmianę limitu w kodzie bez zmiany opisu: model liczyłby na inną liczbę trafień,
    niż dostaje, i źle oceniał, czy zapytanie było zbyt ogólne."""
    assert f"najwyżej {MAX_LINES_PER_SEARCH} linii" in DESCRIPTION


def test_the_description_says_where_a_line_is_cut() -> None:
    """Sprawdza, czy opis narzędzia podaje długość, po której treść linii jest ucinana, równą
    stałej `MAX_TEXT_CHARS`, i znak, którym ucięta linia się kończy.

    Wyłapuje opis rozjechany z kodem: model nie wiedziałby, że linia zakończona tym znakiem
    nie jest cała."""
    assert f"po {MAX_TEXT_CHARS} znakach" in DESCRIPTION
    assert CUT_MARK in DESCRIPTION


def test_the_description_names_the_shortest_word_the_code_accepts() -> None:
    """Sprawdza, czy opis narzędzia mówi, że co najmniej jedno słowo ma mieć trzy znaki, a próg
    w kodzie (`MIN_LONGEST_WORD_CHARS`) wynosi właśnie trzy.

    Wyłapuje zmianę progu w kodzie bez zmiany opisu: model dowiadywałby się o prawdziwym progu
    dopiero z błędu, po zużyciu tury."""
    assert MIN_LONGEST_WORD_CHARS == 3
    assert "jedno słowo ma mieć trzy znaki" in DESCRIPTION


def test_the_description_explains_every_field_of_the_result() -> None:
    """Sprawdza, czy tabelka wyniku w opisie narzędzia wymienia każde pole trafionej linii,
    w tym nazwę funkcji (`lines[].symbol`), i oba pola górnego poziomu.

    Wyłapuje pole dopisane w modelu wyniku bez słowa w opisie: model widziałby przy linii nazwę
    funkcji, ale nie wiedziałby, że może ją podać narzędziu `read_code_symbol`."""
    returns = DESCRIPTION.split("# Co zwraca")[1].split("# Zasady")[0]

    assert set(FindCodeTextResult.model_fields) == {"lines", "omitted_over_limit"}

    fields = ["lines", "omitted_over_limit"]
    fields += [f"lines[].{name}" for name in MatchedLine.model_fields]

    for field in fields:
        assert f"| {field} " in returns, field


def test_the_description_says_what_to_do_with_the_symbol() -> None:
    """Sprawdza, czy zasady w opisie mówią, czym jest `symbol` i któremu narzędziu się go podaje:
    `read_code_symbol`, jako `name`, razem ze ścieżką linii.

    Wyłapuje pole bez instrukcji: nazwa funkcji przy każdej linii kosztuje znaki w każdym
    wyniku, więc ma prowadzić model do odczytu całej funkcji."""
    rules = DESCRIPTION.split("# Zasady")[1]

    assert "`read_code_symbol`" in rules
    assert "jako `name`" in rules
