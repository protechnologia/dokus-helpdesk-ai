"""
Description:
Stałe helpera grafów: pakiet aplikacji, w którym leżą grafy, znacznik tekstu po anonimizacji
i wzór nazwy narzędzia w prompcie.
"""

# Pakiet aplikacji z katalogiem na graf: z niego `graph_module()` importuje pakiet grafu po nazwie.
GRAPHS_PACKAGE = "app.agent_graphs"

# Znacznik zamiast tekstu po anonimizacji w `anonymized_state()`: gdy jest w prompcie, a tekstu
# surowego nie ma, prompt wziął treść z `anonymized`.
ANONYMIZED = "ZANONIMIZOWANE-7f3a"

# Nazwa narzędzia podana w prompcie: w grawisach i zaczyna się od czynności narzędzia. Po tym
# test kontraktu odróżnia nazwy narzędzi od nazw pól, które prompt też pisze w grawisach.
TOOL_NAME_IN_PROMPT = r"`((?:find|read|list|quote|describe|respond)_[a-z_]+)`"
