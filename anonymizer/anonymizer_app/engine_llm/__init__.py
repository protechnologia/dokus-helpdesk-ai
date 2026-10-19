"""
Description:
Klient modelu anonimizującego (Chat Completions zgodne z OpenAI: vLLM, Ollama) i odczyt jego
odpowiedzi. Importuj stąd (`from anonymizer_app.engine_llm import LLMClient`), nie z modułów
w środku. Modele wiadomości i odpowiedzi leżą w `core_model/`, jak wszystkie modele usługi.

| moduł             | co zawiera                                                 |
|-------------------|------------------------------------------------------------|
| `client.py`       | `LLMClient` — jedno wywołanie ze schematem JSON odpowiedzi |
| `answer_items.py` | `answer_items()` — lista z odpowiedzi, także z uciętej     |

Kodu nie dzieli z klientem modelu w `api`: usługi łączy tylko kontrakt ENV, a ten klient nie
zapisuje treści na żadnym poziomie logu.
"""

from anonymizer_app.engine_llm.answer_items import answer_items
from anonymizer_app.engine_llm.client import LLMClient

__all__ = [
    "LLMClient",
    "answer_items",
]
