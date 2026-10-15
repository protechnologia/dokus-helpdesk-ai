"""
Description:
Testy na żywym, płatnym modelu: konfiguracja modelu, graf uruchomiony na nim (jedna sprawa,
wiele spraw naraz, reguły z zestawu domyślnego, pomiar raz na graf) i raport zużycia.

Wejście do modelu i przebieg grafu leżą w `helper.py`, raport z funkcjami, z których składa
linie, w `report.py`, modele danych w `models/` (plik na model), stałe w `constants.py`; testy
importują wszystko z pakietu.
"""

from tests._helpers.live.constants import (
    CUT_MARK,
    LLM_LIVE_MARKER,
    MAX_ARGUMENTS_CHARS,
    MAX_RESULT_TEXT_CHARS,
)
from tests._helpers.live.helper import (
    Measured,
    default_rules,
    live_generation_llm,
    live_state,
    remember_per_graph,
    run_live_cases,
    run_live_graph,
)
from tests._helpers.live.models.live_case import LiveCase
from tests._helpers.live.models.live_usage import LiveUsage
from tests._helpers.live.report import (
    LiveUsageReport,
    arguments_as_text,
    result_as_summary,
    run_as_lines,
    usage_as_text,
)

__all__ = [
    "arguments_as_text",
    "CUT_MARK",
    "default_rules",
    "live_generation_llm",
    "live_state",
    "LiveCase",
    "LiveUsage",
    "LiveUsageReport",
    "LLM_LIVE_MARKER",
    "MAX_ARGUMENTS_CHARS",
    "MAX_RESULT_TEXT_CHARS",
    "Measured",
    "remember_per_graph",
    "result_as_summary",
    "run_as_lines",
    "run_live_cases",
    "run_live_graph",
    "usage_as_text",
]
