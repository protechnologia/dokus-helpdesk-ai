"""
Description:
Cenniki modeli — po jednym pliku na sposób rozliczania. Koszt wywołania liczy klient dostawcy
swoim cennikiem, bo stawki są wiedzą dostawcy, nie domeny (zasada 4).

| plik            | co zawiera                                                        |
|-----------------|-------------------------------------------------------------------|
| `base.py`       | `ModelPrice` i `price()` — wiersz cennika: wejście, wyjście, cache |
| `claude.py`     | cennik Claude'a: cztery klasy tokenów, zapis i odczyt cache       |
| `openai.py`     | cennik OpenAI: wejście, wyjście i odczyt z cache                  |
| `selfhosted.py` | model na własnym sprzęcie: zawsze zero                            |

O czym pamiętać przy zmianach:

- Tabela cen to kopia opublikowanego cennika z datą sprawdzenia w komentarzu. Przy zmianie
  stawek zmienia się datę razem z liczbami.
- Model spoza tabeli to błąd przy budowie klienta, a nie cena zero: koszt 0,00 USD wygląda jak
  odpowiedź.
- Każdy wiersz to jedna linia z trzema NAZWANYMI liczbami, także mnożnikiem odczytu z cache —
  bez wartości domyślnej i bez zapisu pozycyjnego, żeby tabelę dało się porównać z cennikiem
  na oko.
"""
