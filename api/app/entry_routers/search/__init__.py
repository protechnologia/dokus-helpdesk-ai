"""
Description:
Trasy `POST /search` — graf `search`: źródła z `cite()` i zapytania agenta.

W katalogu: trasa (`router.py`, obiekt `router`), modele API tylko tej trasy (`models.py`)
i zamiana stanu końcowego grafu na odpowiedź (`mapping.py`). Obiektu `router` celowo nie
wystawiamy z pakietu: przesłoniłby moduł `router.py` w przestrzeni pakietu, a `main.py` sięga po
niego pełną ścieżką.
"""
