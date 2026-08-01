"""
Description:
Provider-agnostic access to a language model. Import from here (`from app.llm import LLMClient`)
rather than from the submodules — the split between interface, fake and factory is an internal
detail, while this surface is what the domain is allowed to know about a model.
"""

from app.llm.base import LLMClient, LLMCompletion
from app.llm.client_fake import FakeLLMClient
from app.llm.errors import LLMConfigError, LLMError
from app.llm.factory import get_llm_client

__all__ = [
    "FakeLLMClient",
    "LLMClient",
    "LLMCompletion",
    "LLMConfigError",
    "LLMError",
    "get_llm_client",
]
