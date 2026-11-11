"""
Description:
Stałe atrap indeksera zgłoszeń i testów trasy `POST /tickets/closed`.
"""

# Wymiar wektorów atrapy embeddera: mały, bo testy porównują wektory wprost.
VECTOR_SIZE = 4

# Węzły jednego przebiegu grafu bez narzędzi, w kolejności logu: bramki albo karty. Trasa
# zamknięcia oddaje log obu grafów, więc przy przepuszczeniu stoją w nim dwa razy.
GRAPH_NODES = ["anonymize", "agent", "respond"]
