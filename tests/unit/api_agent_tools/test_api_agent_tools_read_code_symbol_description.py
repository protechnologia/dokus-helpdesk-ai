from app.agent_tools.code.read_code_symbol import (
    MAX_CANDIDATES,
    MAX_LINES_PER_SYMBOL,
    FakeReadCodeSymbolTool,
    ReadCodeSymbolResult,
    RequestedSymbol,
    ReturnedSymbolLines,
    SymbolDefinition,
)

# Opis `read_code_symbol` dla modelu podaje trzy rzeczy, które kod trzyma gdzie indziej: limit
# linii na wywołanie, limit listy kandydatów i pola wyniku. Układ opisu sprawdza test kontraktu
# narzędzi; tu pilnujemy tylko tego, żeby opis i kod mówiły to samo.

DESCRIPTION = FakeReadCodeSymbolTool().description

# Pola wyniku pod pełną ścieżką, tak jak stoją w tabelce „Co zwraca". Nazwy pól zagnieżdżonych
# pochodzą z modeli, więc pole dopisane w modelu trafia tu samo.
RESULT_FIELDS = [
    *[f"requested.{name}" for name in RequestedSymbol.model_fields],
    "symbol",
    *[f"symbol.{name}" for name in SymbolDefinition.model_fields],
    *[f"returned.{name}" for name in ReturnedSymbolLines.model_fields],
    "numbered_lines",
    "candidates",
    *[f"candidates[].{name}" for name in SymbolDefinition.model_fields],
    "omitted_over_limit",
]


def test_the_description_names_both_limits_of_the_code() -> None:
    """Sprawdza, czy opis narzędzia podaje modelowi limit linii na wywołanie równy stałej
    `MAX_LINES_PER_SYMBOL` i limit listy kandydatów równy `MAX_CANDIDATES`.

    Wyłapuje zmianę limitu w kodzie bez zmiany opisu: model dowiadywałby się o prawdziwej
    liczbie dopiero z urwanej funkcji albo z uciętej listy."""
    assert f"najwyżej {MAX_LINES_PER_SYMBOL} linii" in DESCRIPTION
    assert f"najwyżej {MAX_CANDIDATES} pozycji" in DESCRIPTION


def test_the_description_explains_every_field_of_the_result() -> None:
    """Sprawdza, czy tabelka wyniku w opisie narzędzia wymienia każde pole, które model dostaje,
    pod pełną ścieżką (na przykład `candidates[].from_line`), i czy wynik nie ma części górnego
    poziomu, o której ten test nie wie.

    Wyłapuje pole dopisane w modelu wyniku bez słowa w opisie: model widziałby je w odpowiedzi,
    ale nie wiedziałby, co znaczy — a od pól kandydata zależy, jak przeczyta właściwą funkcję."""
    returns = DESCRIPTION.split("# Co zwraca")[1].split("# Zasady")[0]

    assert set(ReadCodeSymbolResult.model_fields) == {
        "requested", "symbol", "returned", "numbered_lines", "candidates", "omitted_over_limit",
    }

    for field in RESULT_FIELDS:
        assert f"| {field} " in returns, field


def test_the_description_names_both_notations_of_a_name_with_its_place() -> None:
    """Sprawdza, czy opis podaje modelowi oba zapisy nazwy razem z miejscem, które narzędzie
    przyjmuje: metodę z klasą przez `::` i funkcję z obiektem przez kropkę.

    Wyłapuje opis, który obiecuje zapis nieobsługiwany przez kod albo przemilcza obsługiwany:
    oba przykłady z opisu sprawdza osobno test szukania definicji."""
    arguments = DESCRIPTION.split("# Jak wywoływać")[1].split("# Co zwraca")[0]

    assert "`GeneratorNumeru::nastepnyNumer`" in arguments
    assert "`APP.pisma.wyslijHandler`" in arguments
