import pytest

from app.agent_tools.code.find_code_text import MAX_TEXT_CHARS, shorten_line, symbol_name_at
from app.agent_tools.code.find_code_text.base import CUT_MARK
from app.core_model.code.code_symbol import CodeSymbol
from app.core_model.code.code_symbol_map import CodeSymbolMap

# Treść linii kodu w wyniku `find_code_text`: bez wcięcia i najwyżej `MAX_TEXT_CHARS` znaków.
# Obok treści stoi nazwa funkcji, w której linia leży, brana z mapy symboli.

GENERATOR  = "src/lib/Numeracja/Generator.php"
SYMBOL_MAP = CodeSymbolMap(
    built_on      = "2026-10-13",
    syntax_errors = [],
    files         = {
        GENERATOR: [
            CodeSymbol(name="Generator", scope=None, kind="class", from_line=3, to_line=20),
            CodeSymbol(name="nastepny", scope="Generator", kind="method", from_line=5, to_line=9),
            CodeSymbol(name="formatuj", scope="Generator", kind="method", from_line=11, to_line=19),
        ],
    },
)


@pytest.mark.parametrize(
    ("line", "name"),
    [
        (1,  None),
        (3,  "Generator"),
        (4,  "Generator"),
        (5,  "nastepny"),
        (9,  "nastepny"),
        (10, "Generator"),
        (11, "formatuj"),
        (19, "formatuj"),
        (20, "Generator"),
        (21, None),
    ],
)
def test_a_line_is_named_after_the_innermost_definition_around_it(
    line: int,
    name: str | None,
) -> None:
    """Sprawdza, w której definicji leży linia pliku: w metodzie od jej pierwszej do ostatniej
    linii włącznie, w klasie między metodami, a poza klasą w żadnej.

    Wyłapuje nazwę klasy zamiast metody albo granicę przesuniętą o linię: model prosiłby
    narzędzie `read_code_symbol` o całą klasę albo o sąsiednią metodę zamiast o tę, w której
    stoi znaleziony tekst."""
    assert symbol_name_at(SYMBOL_MAP, GENERATOR, line) == name


def test_a_file_the_map_does_not_know_has_no_names() -> None:
    """Sprawdza, czy linia pliku, którego nie ma w mapie symboli, nie dostaje nazwy.

    Wyłapuje błąd zamiast braku nazwy: szablony, pliki YAML i pliki odrzucone przez parser są
    w paczce, ale nie w mapie, a szukanie ma w nich działać jak dotąd."""
    assert symbol_name_at(SYMBOL_MAP, "src/config/routing.yml", 5) is None


def test_the_indentation_is_dropped() -> None:
    """Sprawdza, czy z treści linii znikają spacje i tabulatory z obu końców, a wnętrze zostaje
    bez zmian, razem z podwójną spacją w środku.

    Wyłapuje linię pokazywaną z wcięciem na kilkanaście spacji, czyli tokeny bez treści, oraz
    przycinanie, które rusza wnętrze linii: model przepisywałby wtedy inny tekst niż w kodzie."""
    assert shorten_line("\t    $a  = 'Brak sekwencji';  ") == "$a  = 'Brak sekwencji';"


def test_a_line_at_the_limit_is_left_whole() -> None:
    """Sprawdza, czy linia mająca dokładnie tyle znaków, ile wynosi limit, wraca w całości i bez
    znaku ucięcia.

    Wyłapuje granicę przesuniętą o jeden znak: linia mieszcząca się w limicie dostawałaby znak
    ucięcia, a model uznawałby, że nie widzi jej końca."""
    line = "x" * MAX_TEXT_CHARS

    assert shorten_line(line) == line


def test_a_longer_line_is_cut_and_marked() -> None:
    """Sprawdza, czy linia dłuższa od limitu o jeden znak wraca ucięta do limitu i zakończona
    znakiem ucięcia.

    Wyłapuje ucięcie bez znaku: model brałby uciętą linię za całą i cytował warunek, którego
    drugiej połowy nie widział. Wyłapuje też linię oddawaną w całości, bo jedna linia sklejonego
    kodu potrafi mieć tysiące znaków."""
    line = "x" * (MAX_TEXT_CHARS + 1)

    assert shorten_line(line) == "x" * MAX_TEXT_CHARS + CUT_MARK
