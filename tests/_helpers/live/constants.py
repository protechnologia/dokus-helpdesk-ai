"""
Description:
Stałe testów na żywym modelu: znacznik, który je wybiera, i to, ile znaków argumentów i wyników
narzędzi trafia do raportu zużycia.
"""

# Znacznik testów wołających prawdziwy, płatny model. Po nim `live_generation_llm()` sprawdza,
# czy testy wybrano jawnie, a fixture w `tests/conftest.py` rozpoznaje test, któremu nie podmienia
# modelu na atrapę.
LLM_LIVE_MARKER = "llm_live"

# Ile znaków argumentów wywołania pokazuje raport. Dłuższe są ucinane, bo narzędzie odpowiedzi
# niesie w nich całą propozycję, a raport ma pokazać przebieg, nie treść.
MAX_ARGUMENTS_CHARS = 300

# Od ilu znaków tekst w wyniku narzędzia raport zastępuje jego długością. Wynik odczytu niesie
# cały wątek albo plik, a z raportu ma być widać, co narzędzie oddało, nie przeczytać to.
MAX_RESULT_TEXT_CHARS = 80

# Znak doklejany do uciętych argumentów, żeby było widać, że w raporcie nie stoją w całości.
CUT_MARK = "…"
