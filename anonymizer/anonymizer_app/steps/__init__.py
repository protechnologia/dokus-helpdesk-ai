"""
Description:
Kroki, z których składa się prawdziwy silnik anonimizacji: każdy przyjmuje tekst i oddaje go ze
znacznikami w miejscu danych, które rozpoznaje. Silnik (p. 19.5) woła je po kolei. Importuje się
z modułów (`from anonymizer_app.steps.replace_patterns import replace_patterns`); ten plik
niczego nie eksportuje.

| plik                  | krok                                                                  |
|-----------------------|-----------------------------------------------------------------------|
| `replace_patterns.py` | dane o stałym kształcie na znaczniki wzorcami z `patterns/` (p. 19.4) |
"""
