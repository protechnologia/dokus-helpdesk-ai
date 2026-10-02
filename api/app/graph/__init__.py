"""
Description:
Grafy funkcji produktu: każdy to anonimizacja → pętla agenta z narzędziami → odpowiedź.
Importuj wspólne elementy stąd (`from app.graph import merge_sources`).

Do czego:
Tutaj (`base.py`) to, czego potrzebują stany wszystkich grafów — dziś reduktor `merge_sources`.
W katalogu każdego grafu: przebieg (`graph.py`), stan (`state.py`), atrapa grafu (`fake.py`),
prompt startowy i opisy narzędzi dla modelu (`.md`). Katalogi grafów powstają w p. 5
(CLAUDE.md -> „Plan i TODO").
"""

from app.graph.base import merge_sources

__all__ = [
    "merge_sources",
]
