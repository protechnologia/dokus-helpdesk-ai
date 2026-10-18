"""
Description:
Modele usługi `anonymizer` — wyłącznie modele, jeden na plik, a plik nazywa się jak jego model.
Importuje się z modułów (`from anonymizer_app.models.found import Found`); ten plik niczego nie
eksportuje.

| plik                    | model               | co opisuje                                |
|-------------------------|---------------------|-------------------------------------------|
| `anonymize_request.py`  | `AnonymizeRequest`  | wejście `POST /anonymize`                 |
| `anonymize_response.py` | `AnonymizeResponse` | wyjście `POST /anonymize` z nazwą silnika |
| `health_response.py`    | `HealthResponse`    | wyjście `GET /health`                     |
| `error_response.py`     | `ErrorResponse`     | jeden kształt każdego obsłużonego błędu   |
| `found.py`              | `Found`             | miejsce danej znalezione przez wzorzec    |
"""
