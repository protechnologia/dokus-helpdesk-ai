"""
Description:
Silnik anonimizacji usługi, niezależny od tego, co pod spodem. Importuj stąd
(`from anonymizer_app.engine import Engine`), nie z modułów w środku.

| moduł        | co zawiera                                                  |
|--------------|-------------------------------------------------------------|
| `base.py`    | kontrakt `Engine`: nazwa, `anonymize()`, wpis w logu        |
| `fake.py`    | `FakeEngine` — oddaje tekst bez zmian                       |
| `factory.py` | `build_engine()` i `get_engine()` po `ANONYMIZATION_ENGINE` |

Błędy silnika leżą w `errors/`, a kroki, z których prawdziwy silnik się składa, w `steps/`.
"""

from anonymizer_app.engine.base import Engine
from anonymizer_app.engine.factory import SUPPORTED_ENGINES, build_engine, get_engine
from anonymizer_app.engine.fake import FAKE_ENGINE_NAME, FakeEngine

__all__ = [
    "FAKE_ENGINE_NAME",
    "SUPPORTED_ENGINES",
    "Engine",
    "FakeEngine",
    "build_engine",
    "get_engine",
]
