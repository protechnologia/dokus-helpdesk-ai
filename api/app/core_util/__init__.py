"""
Description:
Funkcje bezstanowe wspólne dla całej aplikacji, podzielone według RODZAJU wartości, na której
pracują (`time.py`, `text.py`, `html.py` i kolejne), a nie według tego, która warstwa je woła.

Nic tutaj niczego nie rozstrzyga i nie dotyka wejścia ani wyjścia. Funkcja trafia do tego pakietu,
gdy nie należy do dziedziny, nie rozmawia z żadną usługą i jest na tyle ogólna, że następny
wołający ma jej użyć, zamiast pisać ją od nowa — także wtedy, gdy dziś woła ją jedno miejsce.
"""
