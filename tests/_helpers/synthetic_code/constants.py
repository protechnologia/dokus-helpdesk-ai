"""
Description:
Stałe helpera paczki syntetycznej: korzeń repo, katalogi i pliki paczki, polecenie budowy.
"""

from pathlib import Path

# Korzeń repo, od którego liczą się pozostałe ścieżki, więc testy znajdują paczkę niezależnie od
# katalogu, z którego uruchomiono pytest. Ten plik leży w `tests/_helpers/synthetic_code/`.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Katalog zbudowanej paczki syntetycznej, na której stoją testy narzędzi kodu: kod w `repo/`,
# obok metryczka, opis projektu i mapa symboli.
SYNTHETIC_PACKAGE_DIR = REPO_ROOT / "data" / "safe" / "code"

# Źródło aplikacji syntetycznej: z niego testy skryptów budują paczkę w katalogu tymczasowym.
SYNTHETIC_SOURCE_DIR = SYNTHETIC_PACKAGE_DIR / "source"

# Reguły, według których testy skryptów wybierają pliki ze źródła — te same, z którymi buduje się
# paczkę przed testami.
SYNTHETIC_RULES_FILE = SYNTHETIC_PACKAGE_DIR / "rules.json"

# Zestaw zapytań do aplikacji syntetycznej, sekcja na narzędzie: z niego powstają parametry
# testów narzędzi kodu.
SYNTHETIC_CASES_FILE = REPO_ROOT / "data" / "safe" / "golden" / "code-synthetic.json"

# Polecenie, które podaje błąd testu, gdy paczka nie jest zbudowana albo jest nieaktualna, żeby
# dało się ją zbudować bez szukania w dokumentacji.
BUILD_COMMAND = "python scripts/build_code_package.py build data/safe/code/source data/safe/code"
