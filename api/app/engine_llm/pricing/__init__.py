"""
Description:
Cenniki modeli — po jednym pliku na sposób rozliczania. Koszt wywołania liczy klient dostawcy
swoim cennikiem, bo stawki są wiedzą dostawcy, nie domeny (zasada 4).

| plik            | co zawiera                                                          |
|-----------------|---------------------------------------------------------------------|
| `base.py`       | `ModelPrice` i `price()` — wiersz cennika; `cost_usd()` — rachunek  |
| `claude.py`     | cennik Claude'a                                                     |
| `openai.py`     | cennik OpenAI                                                       |
| `selfhosted.py` | model na własnym sprzęcie: zawsze zero                              |

Rachunek jest jeden dla wszystkich dostawców: cztery ROZŁĄCZNE klasy tokenów — świeże wejście,
zapis do cache promptu, odczyt z cache i wyjście — każda po swojej stawce z wiersza modelu.

O czym pamiętać przy zmianach:

- Tabela cen to kopia opublikowanego cennika z datą sprawdzenia w komentarzu. Przy zmianie
  stawek zmienia się datę razem z liczbami.
- Model spoza tabeli to błąd przy budowie klienta, a nie cena zero: koszt 0,00 USD wygląda jak
  odpowiedź.
- Każdy wiersz to jedna linia z czterema NAZWANYMI liczbami: wejście, wyjście oraz mnożniki
  odczytu z cache i zapisu do niego — bez wartości domyślnej i bez zapisu pozycyjnego, żeby
  tabelę dało się porównać z cennikiem na oko. Model bez osobnej stawki zapisu dostaje 1,00.
- Klasy tokenów mają przyjść do `cost_usd()` rozłączne. Dostawca, który podaje tokeny cache
  WEWNĄTRZ licznika wejścia (OpenAI), jest rozdzielany w swoim kliencie.
"""
