"""
Description:
Dostęp do anonimizatora — usługi, przez którą przechodzi każda treść, zanim trafi do modelu
zewnętrznego. Importuj stąd (`from app.engine_anonymization import Anonymizer`).

Do czego:
Pakiet na usługę za granicą procesu, jak `engine_embedding/` (CLAUDE.md -> „Warstwy kodu"): kontrakt
(`base.py`), klient usługi `anonymizer` (`client.py`), atrapa (`fake.py`), fabryka (`factory.py`),
błędy i typ `AnonymizedText`.

| implementacja      | kiedy                     | co robi                                       |
|--------------------|---------------------------|-----------------------------------------------|
| `AnonymizerClient` | zawsze w czasie działania | pyta usługę; wynik atrapy silnika przyjmuje   |
|                    |                           | tylko przy atrapie modelu generującego        |
| `FakeAnonymizer`   | wyłącznie w testach       | oddaje tekst bez zmian, bez usługi            |
"""

from app.engine_anonymization.base import Anonymizer
from app.engine_anonymization.client import AnonymizerClient
from app.engine_anonymization.errors import AnonymizationConfigError, AnonymizationError
from app.engine_anonymization.factory import build_anonymizer
from app.engine_anonymization.fake import FakeAnonymizer
from app.engine_anonymization.models import AnonymizedText, AnonymizerInfo

__all__ = [
    "AnonymizationConfigError",
    "AnonymizationError",
    "AnonymizedText",
    "Anonymizer",
    "AnonymizerClient",
    "AnonymizerInfo",
    "FakeAnonymizer",
    "build_anonymizer",
]
