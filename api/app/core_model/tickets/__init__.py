"""
Description:
Modele zgłoszeń: zgłoszenie źródłowe, sparsowana karta i raporty z pracy na artefaktach. Plik
nazywa się jak jego model. Importuje się z modułów
(`from app.core_model.tickets.parsed_ticket import ParsedTicket`); ten plik niczego nie
eksportuje — `parsed_ticket.py` sięga do `core_service/`, więc import zbiorczy stąd zapętlałby
się z serwisami.

| plik                      | model                       | co opisuje                    |
|---------------------------|-----------------------------|-------------------------------|
| `raw_ticket.py`           | `RawTicket`                 | zgłoszenie źródłowe z wątkiem |
| `raw_comment.py`          | `RawComment`                | jeden komentarz wątku         |
| `parsed_ticket.py`        | `ParsedTicket`              | karta — kontrakt artefaktu    |
| `file_verdict.py`         | `FileVerdict`               | walidacja jednego artefaktu   |
| `validation_report.py`    | `ValidationReport`          | walidacja katalogu artefaktów |
| `quality_verdict.py`      | `QualityVerdict`, `RuleHit` | werdykt filtru o zgłoszeniu   |
| `quality_report.py`       | `QualityReport`             | werdykty filtru dla korpusu   |
| `tickets_index_report.py` | `TicketsIndexReport`        | co zrobiła jedna indeksacja   |
"""
