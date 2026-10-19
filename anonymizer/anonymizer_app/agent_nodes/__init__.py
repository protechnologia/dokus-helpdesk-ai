"""
Description:
Węzły grafu anonimizacji, katalog na węzeł (`node.py`, a przy węzłach z modelem także prompt:
`prompt_system.md` i przykłady w `examples.json`). Na górze pakietu kontrakt `Node` (`base.py`)
i wspólny przebieg węzła, który pyta model (`ask_model.py`). Importuje się z modułów
(`from anonymizer_app.agent_nodes.base import Node`); ten plik niczego nie eksportuje.

| węzeł              | co robi                                                          |
|--------------------|------------------------------------------------------------------|
| `replace_patterns` | dane o stałym kształcie wzorcami z `core_patterns/` (p. 19.4)    |
| `split_chunks`     | tekst po wzorcach na części, które mieszczą się w oknie modelu   |
| `find_persons`     | model wskazuje imiona i nazwiska, kod szuka ich odmian (p. 19.5) |
| `find_addresses`   | model wskazuje adresy bez kotwicy, kod je dopasowuje i odsiewa   |
| `replace_found`    | miejsca osób i adresów na znaczniki                              |

Kolejność i równoległość węzłów ustala graf (`agent_graphs/anonymize/graph.py`).
"""
