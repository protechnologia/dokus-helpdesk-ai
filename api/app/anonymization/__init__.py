"""
Description:
Dostęp do anonimizatora — usługi, przez którą przechodzi każda treść, zanim trafi do modelu
zewnętrznego. Importuj stąd (`from app.anonymization import Anonymizer`).

Do czego:
Pakiet na usługę za granicą procesu, jak `embedding/` (CLAUDE.md -> „Warstwy kodu"): kontrakt
(`base.py`), atrapa (`fake.py`), fabryka (`factory.py`), błędy i typ `AnonymizedText`. Klient
prawdziwej usługi `anonymizer` dochodzi w p. 16 (CLAUDE.md -> „Plan i TODO").
"""

from app.anonymization.base import Anonymizer
from app.anonymization.errors import AnonymizationConfigError, AnonymizationError
from app.anonymization.factory import build_anonymizer
from app.anonymization.fake import FakeAnonymizer
from app.anonymization.models import AnonymizedText

__all__ = [
    "AnonymizationConfigError",
    "AnonymizationError",
    "AnonymizedText",
    "Anonymizer",
    "FakeAnonymizer",
    "build_anonymizer",
]
