"""
Description:
Tabela dokumentacji w Postgresie: klasa i jej SQL w jednym katalogu.

| plik          | co zawiera                                    |
|---------------|-----------------------------------------------|
| `_create.sql` | kolumny tabeli, przeszukiwany tekst i indeks  |
| `_upsert.sql` | zapis wierszy                                 |
| `table.py`    | `DocsTable` — zapis, szukanie i odczyt sekcji |
"""

from app.db_postgres.table.docs.table import DOCS_TABLE, DocsTable

__all__ = [
    "DOCS_TABLE",
    "DocsTable",
]
