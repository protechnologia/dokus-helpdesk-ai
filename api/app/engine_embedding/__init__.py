"""
Description:
Droga `api` do usługi `embedder`. Importuj stąd (`from app.engine_embedding import
EmbeddingClient`), nie z modułów w środku — podział na klienta, model wyniku i błędy to szczegół
pakietu, a to, co stąd wychodzi, jest wszystkim, co kod domeny wie o zamianie tekstu na wektory.

Bez fabryki, inaczej niż `app.engine_llm`: do embeddera jest jedna droga (HTTP), a to, który
MODEL odpowiada — także czy to atrapa — jest konfiguracją usługi `embedder`, nie naszą. Zmienia
się adres, a adres to argument. Nazwę modelu usługa oddaje w każdym wyniku (`Embeddings.model`).
"""

from app.engine_embedding.client import EmbeddingClient
from app.engine_embedding.errors import EmbeddingConfigError, EmbeddingError
from app.engine_embedding.models import Embeddings

__all__ = [
    "EmbeddingClient",
    "EmbeddingConfigError",
    "EmbeddingError",
    "Embeddings",
]
