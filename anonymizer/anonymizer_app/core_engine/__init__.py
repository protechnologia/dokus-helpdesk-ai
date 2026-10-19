"""
Description:
Silnik anonimizacji usługi, niezależny od tego, co pod spodem. Importuj stąd
(`from anonymizer_app.core_engine import Engine`), nie z modułów w środku.

| moduł        | co zawiera                                                       |
|--------------|------------------------------------------------------------------|
| `base.py`    | kontrakt `Engine`: nazwa, `anonymize()`, `aclose()`, wpis w logu |
| `fake.py`    | `FakeEngine` — oddaje tekst bez zmian                            |
| `agent.py`   | `AgentEngine` — graf anonimizacji: wzorce i model (p. 19.5)      |
| `factory.py` | `build_engine()` i `get_engine()` po `ANONYMIZATION_ENGINE`      |

Błędy silnika leżą w `core_errors/`, a graf, na którym działa silnik `agent`, w `agent_graphs/`.
"""

from anonymizer_app.core_engine.agent import AGENT_ENGINE_NAME, AgentEngine
from anonymizer_app.core_engine.base import Engine
from anonymizer_app.core_engine.factory import SUPPORTED_ENGINES, build_engine, get_engine
from anonymizer_app.core_engine.fake import FAKE_ENGINE_NAME, FakeEngine

__all__ = [
    "FAKE_ENGINE_NAME",
    "AGENT_ENGINE_NAME",
    "SUPPORTED_ENGINES",
    "Engine",
    "FakeEngine",
    "AgentEngine",
    "build_engine",
    "get_engine",
]
