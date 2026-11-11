"""
Description:
Trasa `POST /tickets/closed` — zamknięte zgłoszenie wraca do korpusu (p. 30): bramka zamknięcia,
przy „pass” karta z grafu `parse_ticket` i zapis w korpusie z indeksami.

W katalogu: trasa (`router.py`, obiekt `router`), modele API tylko tej trasy (`models.py`)
i zamiana stanów obu grafów oraz raportu korpusu na odpowiedź (`mapping.py`). Obiektu `router`
celowo nie wystawiamy z pakietu: przesłoniłby moduł `router.py` w przestrzeni pakietu, a `main.py`
sięga po niego pełną ścieżką.
"""
