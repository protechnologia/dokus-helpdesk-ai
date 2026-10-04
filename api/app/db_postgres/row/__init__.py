"""
Description:
Wiersze tabel Postgresa: model na tabelę, z polem na każdą kolumnę. Jeden plik na rodzaj danych,
pod tą samą nazwą co plik tabeli w `table/`.

| plik         | klasa       | wiersz tabeli                                              |
|--------------|-------------|------------------------------------------------------------|
| `tickets.py` | `TicketRow` | zgłoszenie: pola sparsowanego rekordu i pełny tekst wątku  |
| `docs.py`    | `DocRow`    | sekcja dokumentacji: opis z metryczki, kolejność i treść   |

W tym samym kształcie wiersz wchodzi do tabeli i z niej wraca — także jako wynik szukania.
Na modele dziedziny (`ParsedTicket`, `DocSection`) przechodzi się metodami wiersza.
"""

from app.db_postgres.row.docs import DocRow
from app.db_postgres.row.tickets import TicketRow

__all__ = [
    "DocRow",
    "TicketRow",
]
