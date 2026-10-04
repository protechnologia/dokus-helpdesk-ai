"""
Description:
Dostęp do anonimizatora — usługi, przez którą przechodzi każda treść, zanim trafi do modelu
zewnętrznego. Importuj stąd (`from app.engine_anonymization import Anonymizer`).

Do czego:
Pakiet na usługę za granicą procesu, jak `engine_embedding/` (CLAUDE.md -> „Warstwy kodu"): kontrakt
(`base.py`), atrapa (`fake.py`), fabryka (`factory.py`), błędy i typ `AnonymizedText`. Klient
prawdziwej usługi `anonymizer` dochodzi w p. 19 (CLAUDE.md -> „Plan i TODO").
"""

from app.engine_anonymization.base import Anonymizer
from app.engine_anonymization.errors import AnonymizationConfigError, AnonymizationError
from app.engine_anonymization.factory import build_anonymizer
from app.engine_anonymization.fake import FakeAnonymizer
from app.engine_anonymization.models import AnonymizedText

__all__ = [
    "AnonymizationConfigError",
    "AnonymizationError",
    "AnonymizedText",
    "Anonymizer",
    "FakeAnonymizer",
    "build_anonymizer",
]
