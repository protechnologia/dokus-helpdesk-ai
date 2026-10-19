"""
Description:
Trasy `POST /gate/close`, `POST /gate/reply` — grafy bramek: werdykt z furtką i wersją reguł.

W katalogu: trasa (`router.py`, obiekt `router`), modele API tylko tej trasy (`models.py`)
i zamiana stanu końcowego grafu na odpowiedź (`mapping.py`). Obiektu `router` celowo nie
wystawiamy z pakietu: przesłoniłby moduł `router.py` w przestrzeni pakietu, a `main.py` sięga po
niego pełną ścieżką.
"""
