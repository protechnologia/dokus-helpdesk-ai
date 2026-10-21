"""
Description:
Stałe helpera grafów: pakiet aplikacji, w którym leżą grafy, znacznik tekstu po anonimizacji,
wzór nazwy narzędzia w prompcie, grafy bez akapitu o znacznikach anonimizacji, grafy, których
opis narzędzia odpowiedzi nie ma jeszcze układu opisu narzędzia, i grafy, których prompt
systemowy nie jest jeszcze podzielony na sekcje.
"""

# Pakiet aplikacji z katalogiem na graf: z niego `graph_module()` importuje pakiet grafu po nazwie.
GRAPHS_PACKAGE = "app.agent_graphs"

# Znacznik zamiast tekstu po anonimizacji w `anonymized_state()`: gdy jest w prompcie, a tekstu
# surowego nie ma, prompt wziął treść z `anonymized`.
ANONYMIZED = "ZANONIMIZOWANE-7f3a"

# Nazwa narzędzia podana w prompcie: w grawisach i zaczyna się od czynności narzędzia. Po tym
# test kontraktu odróżnia nazwy narzędzi od nazw pól, które prompt też pisze w grawisach.
TOOL_NAME_IN_PROMPT = r"`((?:find|read|list|quote|describe|respond)_[a-z_]+)`"

# Grafy, których prompt systemowy nie mówi jeszcze modelowi o znacznikach anonimizacji. Prompt
# parsujący jest kontraktem artefaktu i dostaje ten akapit w p. 31, razem z masowym importem.
WITHOUT_MARKERS_PARAGRAPH = {"parse_ticket"}

# Grafy, których opis narzędzia odpowiedzi nie ma jeszcze układu opisu narzędzia. Opis karty
# zgłoszenia jest kontraktem artefaktu z zamrożonymi frazami i przechodzi na ten układ w p. 24.
WITHOUT_DESCRIPTION_LAYOUT = {"parse_ticket"}

# Grafy, których prompt systemowy nie jest jeszcze podzielony na sekcje („Zadanie", „Zasady",
# „Anonimizacja", „Dane wejściowe"). Prompt parsujący jest kontraktem artefaktu z frazami
# zamrożonymi testem-strażnikiem i przechodzi na ten układ w p. 24.
WITHOUT_PROMPT_SECTIONS = {"parse_ticket"}

# Nagłówki dwóch sekcji, które prompt systemowy każdego grafu ma w jednym brzmieniu.
ANONYMIZATION_HEADING = "# Anonimizacja"
DATA_HEADING          = "# Dane wejściowe"
