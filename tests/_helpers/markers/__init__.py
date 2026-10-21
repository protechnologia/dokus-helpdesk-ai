"""
Description:
Znaczniki anonimizacji w scenariuszach na żywym modelu: znaczniki w tekście (`markers_in()`),
napisy w klamrach, które ani nie są znacznikiem, ani placeholderem z promptu
(`malformed_markers()`), i znaczniki z wejścia, których zabrakło w wyniku (`lost_markers()`).
Używają go oceny scenariuszy bramek i „Popraw".

Logika leży w `helper.py`, stałe w `constants.py`; testy importują wszystko z pakietu.
"""

from tests._helpers.markers.constants import ANONYMIZATION_KINDS, PROMPT_PLACEHOLDERS
from tests._helpers.markers.helper import lost_markers, malformed_markers, markers_in

__all__ = [
    "ANONYMIZATION_KINDS",
    "lost_markers",
    "malformed_markers",
    "markers_in",
    "PROMPT_PLACEHOLDERS",
]
