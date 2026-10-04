"""
Description:
Modele warstwy LLM: to, co idzie do modelu językowego i z niego wraca, w kształcie niezależnym
od dostawcy. Klient każdego dostawcy tłumaczy je na swój format i z powrotem.

| plik            | klasy                                       | co opisuje                       |
|-----------------|---------------------------------------------|----------------------------------|
| `messages.py`   | `ChatMessage`, `ToolCall`, `ToolDefinition` | rozmowa z modelem i narzędzia    |
| `completion.py` | `LLMCompletion`                             | jedna odpowiedź z rozliczeniem   |
| `usage.py`      | `LLMUsage`                                  | zużycie modelu w całym przebiegu |

Modele leżą tutaj, a nie w `core_model/`: opisują rozmowę z jedną usługą zewnętrzną
(CLAUDE.md -> „Warstwy kodu").
"""

from app.engine_llm.models.completion import LLMCompletion
from app.engine_llm.models.messages import ChatMessage, ToolCall, ToolDefinition
from app.engine_llm.models.usage import LLMUsage

__all__ = [
    "ChatMessage",
    "LLMCompletion",
    "LLMUsage",
    "ToolCall",
    "ToolDefinition",
]
