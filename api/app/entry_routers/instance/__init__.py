"""
Description:
Trasa `GET /instance` — na czym stoi ta instancja: model generujący i stan indeksów, na których
stoją narzędzia agenta. Czyta ją belka frontu pokazowego.

W katalogu: trasa (`router.py`, obiekt `router`), modele API tylko tej trasy (`models.py`)
i zamiana stanu instancji na odpowiedź (`mapping.py`). Obiektu `router` celowo nie wystawiamy
z pakietu: przesłoniłby moduł `router.py` w przestrzeni pakietu, a `main.py` sięga po niego pełną
ścieżką.
"""
