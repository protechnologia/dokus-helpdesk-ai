"""
Description:
Stałe scenariuszy rozpoznania (`search`): plik zestawu, klucz metryczki i nazwy narzędzi kodu,
po których ocena czyta rozmowę.
"""

import re
from pathlib import Path

# Plik zestawu, który wczytuje się, gdy test nie poda innego. Ścieżka od korzenia repo, bo z niego
# uruchamia się pytest.
SEARCH_FILE = Path("data/safe/golden/search.json")

# Klucz metryczki zestawu: przy wczytywaniu sekcji jest pomijany, bo nie nazywa żadnego grafu.
META_KEY = "meta"

# Narzędzie cytowania kodu: z jego wyników ocena bierze cytowane fragmenty i ich role.
QUOTE_TOOL = "quote_code"

# Narzędzia, których wynik niesie treść linii kodu: tylko po nich linia liczy się jako odczytana.
# Linia widziana w wyniku szukania odczytana nie jest — szukanie oddaje jedną linię bez otoczenia.
READ_TOOLS = ("read_code_file", "read_code_symbol")

# Narzędzie spisu katalogu kodu: raport liczy jego wywołania w każdej sprawie.
LIST_TOOL = "list_code_files"

# Rola cytowania, które tworzy źródło: fragment wskazany jako przyczyna opisanego zachowania.
CAUSE_ROLE = "cause"

# Komunikat z ekranu w zgłoszeniu: tekst w polskim cudzysłowie „…”. Po nim test zestawu sprawdza,
# czy komunikat stoi w wymaganym pliku przyczyny albo — w sprawie „nigdzie” — w żadnym pliku paczki.
QUOTED_MESSAGE = re.compile(r"„([^”]+)”")
