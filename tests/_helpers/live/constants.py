"""
Description:
Stałe testów na żywym modelu: znacznik, który je wybiera, to, ile znaków argumentów i wyników
narzędzi trafia do raportu zużycia, dostawca bez kosztu i zgłoszenie jednej sprawy testu
okablowania grafów.
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

# Dostawca self-hosted: nasz sprzęt nie nalicza tokenów, więc koszt sprawy na nim to zero. Po nim
# test okablowania grafów rozpoznaje, czy koszt sprawy ma być zerowy.
PROVIDER_SELFHOSTED = "ollama"

# Zmyślone zgłoszenie z komunikatem z ekranu do sprawy `suggest_solution` z materiałem tylko
# w kodzie. Ten komunikat stoi w zmyślonym kodzie atrap (`agent_tools/code/fake_code.py`), a nie ma
# go w żadnym zgłoszeniu ani instrukcji.
TICKET_WITH_MESSAGE = (
    "Od rana przy rejestracji pisma przychodzącego wyskakuje komunikat "
    "„Brak sekwencji numeracji dla roku 2026\". Wczoraj rejestracja działała bez problemu."
)
