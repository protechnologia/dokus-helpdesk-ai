"""
Description:
Embedding w testach: nazwy modeli embeddera, odpowiedź usługi `embedder` w kształcie kontraktu
(`embedder_answer()`) i payload punktu Qdranta z nazwą modelu (`with_model()`). Używają go testy
klienta embeddera, punktów, trafień i kolekcji Qdranta, narzędzi wektorowych i indekserów.

Logika leży w `helper.py`, stałe w `constants.py`; testy importują wszystko z pakietu.
"""

from tests._helpers.embedding.constants import EMBEDDING_MODEL, OTHER_MODEL
from tests._helpers.embedding.helper import embedder_answer, with_model

__all__ = [
    "EMBEDDING_MODEL",
    "OTHER_MODEL",
    "embedder_answer",
    "with_model",
]
