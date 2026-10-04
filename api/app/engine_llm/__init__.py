"""
Description:
Dostęp do modelu językowego niezależny od dostawcy. Importuj stąd (`from app.engine_llm import
LLMClient`), nie z podmodułów — podział na interfejs, atrapę i fabrykę to szczegół wewnętrzny,
a ta powierzchnia to wszystko, co domena może wiedzieć o modelu.
"""

from app.engine_llm.base import LLMClient, LLMCompletion
from app.engine_llm.client_fake import FakeLLMClient
from app.engine_llm.errors import LLMConfigError, LLMError
from app.engine_llm.factory import get_llm_client
from app.engine_llm.messages import ChatMessage, ToolCall, ToolDefinition

__all__ = [
    "ChatMessage",
    "FakeLLMClient",
    "LLMClient",
    "LLMCompletion",
    "LLMConfigError",
    "LLMError",
    "ToolCall",
    "ToolDefinition",
    "get_llm_client",
]
