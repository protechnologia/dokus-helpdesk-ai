"""
Description:
Narzędzie na prawdziwej tabeli Postgresa z podmienionym klientem (`ScriptedPostgres`).

Logika leży w `helper.py`; testy importują wszystko z pakietu.
"""

from tests._helpers.postgres.helper import (
    ScriptedPostgres,
)

__all__ = [
    "ScriptedPostgres",
]
