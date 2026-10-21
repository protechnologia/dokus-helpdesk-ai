"""
Description:
Opisy narzędzi w testach: układ opisu (`DESCRIPTION_SECTIONS`), wspólny dla narzędzi agenta
i narzędzi odpowiedzi grafów, oraz typy argumentów z tabelki opisu (`argument_types()`) i ze
schematu (`schema_types()`) w jednym zapisie. Używają go testy kontraktu narzędzi i kontraktu
grafów.

Logika leży w `helper.py`, stałe w `constants.py`; testy importują wszystko z pakietu.
"""

from tests._helpers.tool_descriptions.constants import DESCRIPTION_SECTIONS, NULLABLE_SUFFIX
from tests._helpers.tool_descriptions.helper import argument_types, schema_types

__all__ = [
    "argument_types",
    "DESCRIPTION_SECTIONS",
    "NULLABLE_SUFFIX",
    "schema_types",
]
