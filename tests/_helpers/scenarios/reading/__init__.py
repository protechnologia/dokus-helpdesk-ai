"""
Description:
Zestaw scenariuszy czytania znalezionego materiału, ocena odpowiedzi i raport.

Logika leży w `helper.py`, modele danych w `models/` (plik na model), stałe
w `constants.py`, raport w `report.py`, a przebieg spraw na żywym modelu w `measure.py`;
testy importują wszystko z pakietu. Próbki do testów samego helpera leżą w `samples.py`
i pakiet ich nie wystawia.
"""

from tests._helpers.scenarios.reading.constants import (
    CASES_KEY,
    CODE_TOOLS,
    EXCLUSION_WORDS,
    NEGATED_EXCLUSION,
    READERS,
    READING_FILE,
)
from tests._helpers.scenarios.reading.helper import (
    case_keys,
    code_calls,
    excluded_in_notes,
    found_material,
    judge_reading_case,
    material_text,
    material_units,
    reading_cases,
    reading_sections,
)
from tests._helpers.scenarios.reading.measure import ReadingOutcomesOf, measure_reading_cases
from tests._helpers.scenarios.reading.models.reading_case import ReadingCase
from tests._helpers.scenarios.reading.models.reading_outcome import ReadingOutcome
from tests._helpers.scenarios.reading.models.reading_section import ReadingSection
from tests._helpers.scenarios.reading.report import ReadingReport

__all__ = [
    "case_keys",
    "CASES_KEY",
    "code_calls",
    "CODE_TOOLS",
    "excluded_in_notes",
    "EXCLUSION_WORDS",
    "found_material",
    "judge_reading_case",
    "material_text",
    "material_units",
    "measure_reading_cases",
    "NEGATED_EXCLUSION",
    "READERS",
    "reading_cases",
    "READING_FILE",
    "reading_sections",
    "ReadingCase",
    "ReadingOutcome",
    "ReadingOutcomesOf",
    "ReadingReport",
    "ReadingSection",
]
