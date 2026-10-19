"""
Description:
Trasy `POST /suggest`, `GET /variants` — grafy `suggest_*` z rejestru: propozycja w wybranym
wariancie.

W katalogu: trasa (`router.py`, obiekt `router`), modele API tylko tej trasy (`models.py`)
i zamiana stanu końcowego grafu na odpowiedź (`mapping.py`). Obiektu `router` celowo nie
wystawiamy z pakietu: przesłoniłby moduł `router.py` w przestrzeni pakietu, a `main.py` sięga po
niego pełną ścieżką.
"""
