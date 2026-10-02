"""
Description:
Dostęp do anonimizatora — usługi, przez którą przechodzi każda treść, zanim trafi do modelu
zewnętrznego. Importuj stąd (`from app.anonymization import AnonymizedText`).

Do czego:
Pakiet na usługę za granicą procesu, jak `embedding/` (CLAUDE.md -> „Warstwy kodu"): interfejs,
klient, atrapa i ich modele w jednym katalogu. Dziś jest tu tylko typ `AnonymizedText`, bo
potrzebuje go stan grafu; atrapa anonimizatora powstaje w p. 4, klient usługi w p. 16
(CLAUDE.md -> „Plan i TODO").
"""

from app.anonymization.models import AnonymizedText

__all__ = [
    "AnonymizedText",
]
