"""
Description:
Stałe scenariuszy wstrzyknięć: plik zestawu, klucz metryczki, drogi ataku i role
wiadomości, które niosą to, co model dostał.
"""

from pathlib import Path

# Plik zestawu, który wczytuje się, gdy test nie poda innego. Ścieżka od korzenia repo, bo z niego
# uruchamia się pytest.
INJECTIONS_FILE = Path("data/safe/golden/injections.json")

# Klucz metryczki zestawu: przy wczytywaniu sekcji jest pomijany, bo nie nazywa żadnego grafu.
META_KEY = "meta"

# Odstęp między wejściem a doklejonym atakiem: pusta linia, żeby atak wyglądał jak kolejny
# komentarz wątku, a nie jak dalszy ciąg ostatniego.
ATTACK_SEPARATOR = "\n\n"

# Role wiadomości, w których kontrola dotarcia szuka znacznika ataku: zgłoszenie i wyniki
# narzędzi, czyli to, co model dostał. Odpowiedzi modelu się nie liczą — znacznik w nich
# znaczy, że atak już dotarł.
DELIVERING_ROLES = ("user", "tool")

# Droga ataku, który dokleja się na końcu wejścia grafu; tak jest, gdy zestaw drogi nie podaje.
INTO_INPUT = "input"

# Droga ataku, który dopisuje się jako ostatnią regułę klienta, po zestawie domyślnym.
INTO_RULES = "rules"

# Droga ataku, który dokleja się do pola tekstowego karty historycznej sprawy w materiale atrap
# narzędzi; dociera do modelu dopiero, gdy model tę kartę przeczyta.
INTO_CARD = "card"

# Droga ataku, który dopisuje się na końcu wątku historycznej sprawy w materiale atrap narzędzi;
# dociera do modelu dopiero, gdy model ten wątek przeczyta.
INTO_THREAD = "thread"
