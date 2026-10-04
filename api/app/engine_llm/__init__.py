"""
Description:
Dostęp do modelu językowego niezależny od dostawcy. Importuj stąd (`from app.engine_llm import
LLMClient`), nie z podmodułów — podział na interfejs, atrapę i fabrykę to szczegół wewnętrzny,
a ta powierzchnia to wszystko, co domena może wiedzieć o modelu.

| gdzie        | co zawiera                                                        |
|--------------|-------------------------------------------------------------------|
| `base.py`    | `LLMClient` — interfejs, przez który reszta aplikacji woła model  |
| `factory.py` | `get_llm_client()` — klient po `LLM_PROVIDER`, z fail-fast        |
| `client/`    | klienci dostawców, plik na dostawcę; jedyne miejsce na ich SDK    |
| `pricing/`   | cenniki modeli i liczenie kosztu wywołania                        |
| `models/`    | wiadomości, wynik wywołania i zużycie w przebiegu                 |
| `errors.py`  | `LLMError`, `LLMConfigError`                                      |
"""

from app.engine_llm.base import LLMClient
from app.engine_llm.client.fake import FakeLLMClient
from app.engine_llm.errors import LLMConfigError, LLMError
from app.engine_llm.factory import get_llm_client
from app.engine_llm.models import (
    ChatMessage,
    LLMCompletion,
    LLMUsage,
    ToolCall,
    ToolDefinition,
)

__all__ = [
    "ChatMessage",
    "FakeLLMClient",
    "LLMClient",
    "LLMCompletion",
    "LLMConfigError",
    "LLMError",
    "LLMUsage",
    "ToolCall",
    "ToolDefinition",
    "get_llm_client",
]
