"""
Description:
Stałe scenariuszy czytania znalezionego materiału: plik zestawu, klucz listy spraw, narzędzia
kodu, których wywołania liczy raport, słowa wykluczenia w uwagach z ich zaprzeczeniem i narzędzia
odczytu materiałów.
"""

import re
from pathlib import Path

# Plik zestawu, który wczytuje się, gdy test nie poda innego. Ścieżka od korzenia repo, bo z niego
# uruchamia się pytest.
READING_FILE = Path("data/safe/golden/reading.json")

# Klucz listy spraw zestawu; obok niego stoi tylko metryczka. Sprawa sama mówi w polu `graphs`,
# na których grafach idzie, więc zestaw nie ma sekcji na graf.
CASES_KEY = "cases"

# Narzędzia kodu aplikacji: raport liczy ich wywołania w każdej sprawie, bo w sprawie
# organizacyjnej `search` ma kodu nie sprawdzać (p. 70). Test zestawu pilnuje, że lista obejmuje
# każde narzędzie kodu z `TOOL_NAMES` grafu.
CODE_TOOLS = (
    "describe_code",
    "find_code_text",
    "list_code_files",
    "read_code_file",
    "read_code_symbol",
    "quote_code",
)

# Słowa, po których linia uwag nazywa przyczynę wykluczoną: licznik stoi wtedy, gdy w jednej linii
# jest fakt i któreś z tych słów. Porównanie bez wielkich liter i polskich znaków, jak fakty.
EXCLUSION_WORDS = (
    "wyklucz",
    "odpada",
    "nie pasuje",
    "nie dotyczy",
    "mało prawdopodobn",
)

# Słowo wykluczenia z zaprzeczeniem tuż przed nim — „nie wyklucza”, „niewykluczone”, „nie odpada”.
# Takie wystąpienie licznik wycina z linii, zanim szuka w niej słowa wykluczenia: w pierwszych
# przebiegach dwa z trzech trafień licznika stały na linii, która mówiła, że przyczyny NIE
# wykluczono. Granica słowa przed „nie”, żeby przysłówek („jednoznacznie wyklucza”) nie wyglądał na
# zaprzeczenie.
NEGATED_EXCLUSION = re.compile(r"\bnie\s*(?:wyklucz|odpad)\w*")

# Narzędzia, których odczyt tworzy źródło danego materiału: klucz źródła z zestawu musi wskazywać
# materiał, który graf sprawy umie przeczytać.
READERS = {
    "tickets": ("read_tickets_card", "read_tickets_thread"),
    "docs":    ("read_docs",),
}
