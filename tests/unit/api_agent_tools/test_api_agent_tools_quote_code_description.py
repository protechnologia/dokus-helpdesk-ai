from typing import get_args

from app.agent_tools.code.quote_code import MAX_LINES_PER_QUOTE, FakeQuoteCodeTool, QuoteRole

# Opis `quote_code` dla modelu podaje dwie rzeczy, które kod trzyma gdzie indziej: limit długości
# fragmentu i nazwy ról. Układ opisu sprawdza test kontraktu narzędzi; tu pilnujemy tylko tego,
# żeby opis i kod mówiły to samo.

DESCRIPTION = FakeQuoteCodeTool().description


def test_the_description_names_the_fragment_limit_of_the_code() -> None:
    """Sprawdza, czy opis narzędzia podaje modelowi limit długości fragmentu równy stałej
    `MAX_LINES_PER_QUOTE`, w zdaniu „najwyżej … linii".

    Wyłapuje zmianę limitu w kodzie bez zmiany opisu: model dowiadywałby się o prawdziwym limicie
    dopiero z błędu, po zużyciu tury."""
    assert f"najwyżej {MAX_LINES_PER_QUOTE} linii" in DESCRIPTION


def test_the_description_explains_every_role() -> None:
    """Sprawdza, czy opis narzędzia wymienia każdą rolę cytowania, którą przyjmuje model
    zapytania.

    Wyłapuje rolę dopisaną w kodzie bez słowa w opisie: model widziałby ją w schemacie argumentów,
    ale nie wiedziałby, co znaczy ani czy robi z cytowania źródło."""
    for role in get_args(QuoteRole):
        assert f"`{role}`" in DESCRIPTION
