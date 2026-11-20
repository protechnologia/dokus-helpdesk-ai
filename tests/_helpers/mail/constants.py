"""
Description:
Stałe helpera słownika maili: katalog słownika zmyślonego, jego źródło i polecenie budowy.
"""

from pathlib import Path

# Korzeń repo, od którego liczą się pozostałe ścieżki, więc testy znajdują słownik niezależnie
# od katalogu, z którego uruchomiono pytest. Ten plik leży w `tests/_helpers/mail/`.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Katalog słownika zmyślonego: `slownik.json`, `nazwy.json` i zmyślone wątki w `raw-db/`,
# z których powstał słownik.
SAFE_MAIL_DIR = REPO_ROOT / "data" / "safe" / "mail"

# Nazwa dostawcy w słowniku zmyślonym, tak jak stoi w `nazwy.json`.
VENDOR_NAME = "Przykładsoft Sp. z o.o."

# Polecenie, które podaje błąd testu, gdy słownik zmyślony rozjechał się ze swoim źródłem, żeby
# dało się go zbudować od nowa bez szukania w dokumentacji.
BUILD_COMMAND = (
    "python scripts/build_mail_dictionary.py build data/safe/mail data/safe/mail --min-threads 2"
)
