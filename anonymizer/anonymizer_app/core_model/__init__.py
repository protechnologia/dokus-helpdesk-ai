"""
Description:
Modele usługi `anonymizer` — wyłącznie modele, jeden na plik, a plik nazywa się jak jego model.
Importuje się z modułów (`from anonymizer_app.core_model.found import Found`); ten plik niczego nie
eksportuje.

| plik                    | model               | co opisuje                                |
|-------------------------|---------------------|-------------------------------------------|
| `anonymize_request.py`  | `AnonymizeRequest`  | wejście `POST /anonymize`                 |
| `anonymize_response.py` | `AnonymizeResponse` | wyjście `POST /anonymize` z nazwą silnika |
| `health_response.py`    | `HealthResponse`    | wyjście `GET /health`                     |
| `error_response.py`     | `ErrorResponse`     | jeden kształt każdego obsłużonego błędu   |
| `found.py`              | `Found`             | miejsce danej znalezione przez węzeł      |
| `chat_message.py`       | `ChatMessage`       | wiadomość rozmowy z modelem               |
| `llm_answer.py`         | `LLMAnswer`         | odpowiedź modelu i to, czy ją ucięto      |
| `log_entry.py`          | `LogEntry`          | wpis przebiegu grafu anonimizacji         |
| `prompt_example.py`     | `PromptExample`     | przykład z promptu węzła                  |
"""
