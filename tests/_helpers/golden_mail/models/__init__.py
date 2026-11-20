"""
Description:
Modele golden setu kanału „Automat mailowy” i pomiaru czyszczenia na nim. Plik nazywa się jak
jego model; pakiet helpera importuje z modułów, a ten plik niczego nie eksportuje.

| plik                           | model                     | co opisuje                         |
|--------------------------------|---------------------------|------------------------------------|
| `golden_mail_ticket.py`        | `GoldenMailTicket`        | zgłoszenie: `useful` i pola wątku  |
| `golden_mail_field.py`         | `GoldenMailField`         | pole: autor i oznaczenia linii     |
| `mail_label_counts.py`         | `MailLabelCounts`         | linie i słowa jednej etykiety,     |
|                                |                           | które zostały i które zniknęły     |
| `mail_cleaning_measurement.py` | `MailCleaningMeasurement` | przejście normalizera po zestawie  |
"""
