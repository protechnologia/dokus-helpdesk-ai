"""
Description:
Wspólne węzły grafów. Importuj stąd (`from app.nodes import Node`).

Do czego:
Kontrakt węzła (`base.py`). Stanu tu nie ma — każdy graf ma własny `state.py` z pełnym modelem
stanu, a wspólny reduktor `merge_sources` leży w `app/graph/base.py`. W katalogu każdego węzła:
implementacja (`node.py`) i atrapa (`fake.py`). Węzeł używany przez jeden graf mieszka
w katalogu tego grafu, nie tutaj.

Węzły (CLAUDE.md -> „Plan i TODO", blok 0; `anonymize` właściwy, reszta atrapy — właściwe p. 9–11):

| węzeł       | co robi                                                                  |
|-------------|--------------------------------------------------------------------------|
| `anonymize` | wejście → `AnonymizedText`, fail-closed; bez atrapy węzła (p. 4)         |
| `agent`     | tura modelu z narzędziami; decyzja: dalej pętla czy odpowiedź            |
| `run_tools` | wywołania z listy dozwolonych; tekst do `messages`, źródła do `sources`  |
| `respond`   | walidacja do modelu wyjścia, jeden retry, `requires_hits`                |
"""

from app.nodes.base import Node

__all__ = [
    "Node",
]
