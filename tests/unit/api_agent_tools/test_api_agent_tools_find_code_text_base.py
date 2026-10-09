from app.agent_tools.code.find_code_text import MAX_TEXT_CHARS, shorten_line
from app.agent_tools.code.find_code_text.base import CUT_MARK

# Treść linii kodu w wyniku `find_code_text`: bez wcięcia i najwyżej `MAX_TEXT_CHARS` znaków.


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
