"""
Description:
Stałe helpera opisów narzędzi: układ opisu i nazwy typów z tabelki argumentów.
"""

# Nagłówki opisu narzędzia, w tej kolejności: ten sam układ mają opisy narzędzi agenta
# (`description.md`) i opisy narzędzi odpowiedzi grafów (`respond_tool.md`), bo model czyta je
# wszystkie naraz i w każdym szuka argumentów, wyniku i zasad w tym samym miejscu.
DESCRIPTION_SECTIONS = ["# Do czego służy", "# Jak wywoływać", "# Co zwraca", "# Zasady"]

# Dopisek typu pola, które przyjmuje `null` jako odpowiedź, a nie tylko jako brak argumentu.
# Słowem, a nie znakiem `|`, bo ten kończyłby komórkę tabelki.
NULLABLE_SUFFIX = " albo null"
