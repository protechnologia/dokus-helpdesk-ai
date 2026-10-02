"""
Description:
Trasy `GET /health` — sonda żywotności; mówi tylko o samym API, nigdy o zależnościach.

W katalogu: trasa (`router.py`, obiekt `router`) i modele API tylko tej trasy (`models.py`).
Obiektu `router` celowo nie wystawiamy z pakietu: przesłoniłby moduł `router.py` w przestrzeni
pakietu, a `main.py` sięga po niego pełną ścieżką.
"""
