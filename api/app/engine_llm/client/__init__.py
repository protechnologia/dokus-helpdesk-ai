"""
Description:
Klienci dostawców modelu językowego — po jednym pliku na dostawcę. Każdy jest jedynym miejscem,
w którym wolno importować SDK swojego dostawcy (zasada 4).

| plik        | klasa             | dostawca                                             |
|-------------|-------------------|------------------------------------------------------|
| `claude.py` | `ClaudeLLMClient` | API Claude'a                                         |
| `openai.py` | `OpenAILLMClient` | API OpenAI i każdy endpoint z nim zgodny             |
| `ollama.py` | `OllamaLLMClient` | model self-hosted (Ollama, także na RunPodzie)       |
| `fake.py`   | `FakeLLMClient`   | atrapa: nic nie wysyła, nic nie kosztuje             |

Ten plik celowo niczego nie importuje. SDK dostawców ładują się po kilka sekund, więc klienta
bierze się pełną ścieżką (`from app.engine_llm.client.claude import ClaudeLLMClient`) i tylko
tam, gdzie jest potrzebny — robi to fabryka (CLAUDE.md -> „Warstwa LLM").
"""
