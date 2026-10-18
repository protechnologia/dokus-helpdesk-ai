"""
Description:
Błędy usługi `anonymizer` i ich obsługa: plik na błąd, nazwany jak jego klasa, oraz handlery
wyjątków. Importuje się z modułów
(`from anonymizer_app.errors.engine_error import EngineError`); ten plik niczego nie eksportuje.

| plik                     | co zawiera                                                     |
|--------------------------|----------------------------------------------------------------|
| `engine_error.py`        | `EngineError` — awaria silnika w trakcie żądania (503)         |
| `engine_config_error.py` | `EngineConfigError` — błędna konfiguracja silnika przy starcie |
| `handlers.py`            | handlery wyjątków, wspólny kształt błędu, `REQUEST_ID_HEADER`  |
"""
