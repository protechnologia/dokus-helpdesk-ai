import dataclasses


@dataclasses.dataclass(frozen=True)
class RuleViolation:
    """Reguła wysyłki, którą według oceniających łamie wiadomość z zestawu, z powodem."""

    rule:   int  # numer reguły w zestawie domyślnym, od 1; np. 5
    reason: str  # jednym zdaniem, co ją łamie; np. "Brak polskiej litery: „prosze”."
