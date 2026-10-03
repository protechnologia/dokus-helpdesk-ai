"""
Description:
Tabela zgłoszeń w Postgresie: klasa i jej SQL w jednym katalogu.

| plik          | co zawiera                                         |
|---------------|----------------------------------------------------|
| `_create.sql` | kolumny tabeli, przeszukiwany tekst i indeks       |
| `_upsert.sql` | zapis wierszy                                      |
| `table.py`    | `TicketsTable` — zapis, szukanie i odczyt zgłoszeń |
"""

from app.db.table.tickets.table import TicketsTable

__all__ = [
    "TicketsTable",
]
