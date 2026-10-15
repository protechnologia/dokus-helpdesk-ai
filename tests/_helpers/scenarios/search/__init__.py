"""
Description:
Zestaw scenariuszy rozpoznania (`search`), narzędzia sprawy, cytowania kodu z rozmowy, ocena
sprawy i raport.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe
w `constants.py`, raport w `report.py`, a przebieg spraw na żywym modelu w `measure.py`;
testy importują wszystko z pakietu. Próbki do testów samego helpera leżą w `samples.py`
i pakiet ich nie wystawia.
"""

from tests._helpers.scenarios.search.constants import (
    CAUSE_ROLE,
    LIST_TOOL,
    META_KEY,
    QUOTE_TOOL,
    QUOTED_MESSAGE,
    READ_TOOLS,
    SEARCH_FILE,
)
from tests._helpers.scenarios.search.helper import (
    case_tools,
    code_quotes,
    judge_search_case,
    listing_count,
    quoted_messages,
    search_sections,
)
from tests._helpers.scenarios.search.measure import (
    SearchOutcomesOf,
    measure_search_cases,
)
from tests._helpers.scenarios.search.models.code_fragment import CodeFragment
from tests._helpers.scenarios.search.models.code_quote import CodeQuote
from tests._helpers.scenarios.search.models.search_case import SearchCase
from tests._helpers.scenarios.search.models.search_outcome import SearchOutcome
from tests._helpers.scenarios.search.models.search_section import SearchSection
from tests._helpers.scenarios.search.report import SearchReport

__all__ = [
    "case_tools",
    "CAUSE_ROLE",
    "code_quotes",
    "CodeFragment",
    "CodeQuote",
    "judge_search_case",
    "LIST_TOOL",
    "listing_count",
    "measure_search_cases",
    "META_KEY",
    "QUOTE_TOOL",
    "QUOTED_MESSAGE",
    "quoted_messages",
    "READ_TOOLS",
    "SEARCH_FILE",
    "search_sections",
    "SearchCase",
    "SearchOutcome",
    "SearchOutcomesOf",
    "SearchReport",
    "SearchSection",
]
