"""
Description:
Aplikacja syntetyczna: zbudowana paczka, jej źródło i reguły, opis projektu, mapa symboli
i zapytania z zestawu syntetycznego.

Logika leży w `helper.py`, stałe w `constants.py`; testy importują wszystko z pakietu.
"""

from tests._helpers.synthetic_code.constants import (
    BUILD_COMMAND,
    REPO_ROOT,
    SEARCH_TIMEOUT_SECONDS,
    SYNTHETIC_CASES_FILE,
    SYNTHETIC_PACKAGE_DIR,
    SYNTHETIC_RULES_FILE,
    SYNTHETIC_SOURCE_DIR,
)
from tests._helpers.synthetic_code.helper import (
    line_of,
    synthetic_absent_paths,
    synthetic_code_cases,
    synthetic_code_description,
    synthetic_code_package,
    synthetic_code_symbols,
    synthetic_code_texts,
    synthetic_code_tools,
)

__all__ = [
    "BUILD_COMMAND",
    "line_of",
    "REPO_ROOT",
    "SEARCH_TIMEOUT_SECONDS",
    "synthetic_absent_paths",
    "SYNTHETIC_CASES_FILE",
    "synthetic_code_cases",
    "synthetic_code_description",
    "synthetic_code_package",
    "synthetic_code_symbols",
    "synthetic_code_texts",
    "synthetic_code_tools",
    "SYNTHETIC_PACKAGE_DIR",
    "SYNTHETIC_RULES_FILE",
    "SYNTHETIC_SOURCE_DIR",
]
