"""
Description:
Stałe scenariuszy wstrzyknięć: plik zestawu, klucz metryczki, drogi ataku, role wiadomości,
które niosą to, co model dostał, i pole z listą źródeł.
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

# Pole, pod którym ocena dokłada do pól wyniku listę źródeł ze stanu grafu z narzędziami wiedzy,
# jako klucze `materiał:identyfikator`. Dzięki temu źródło, które atak kazał zacytować, da się
# chronić jak pole wyniku, choć model go nie pisze: lista powstaje z wywołań odczytu.
SOURCES_FIELD = "sources"

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

# Narzędzie, które graf musi dawać modelowi, żeby atak w materiale daną drogą do niego dotarł:
# atak w karcie czyta odczyt karty, a atak w wątku — odczyt wątku.
READER_OF = {
    INTO_CARD:   "read_tickets_card",
    INTO_THREAD: "read_tickets_thread",
}
