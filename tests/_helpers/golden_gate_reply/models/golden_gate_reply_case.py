import dataclasses

from tests._helpers.golden_gate_reply.models.rule_violation import RuleViolation


@dataclasses.dataclass(frozen=True)
class GoldenGateReplyCase:
    """Wiadomość z zestawu bramki wysyłki (`graph-gate-reply.json`): skąd wzięta i które reguły
    wysyłki łamie według oceniających."""

    ticket_id:  str                        # np. "23921"
    comment:    int                        # numer komentarza konsultanta w wątku, od 1
    stratum:    str                        # warstwa doboru, np. "random" (lista w `STRATA`)
    digest:     str                        # skrót wiadomości: etykiety opisują ten tekst
    violations: tuple[RuleViolation, ...]  # łamane reguły z powodem; pusta przy poprawnej
    doubtful:   bool                       # przypadek graniczny: oceniający nie był pewny
    doubt:      str | None                 # czego nie był pewny; None przy wpisie pewnym

    @property
    def broken_rules(self) -> tuple[int, ...]:
        """
        Description:
        Numery reguł, które łamie wiadomość, rosnąco.

        Example args:
            (brak)

        Example result:
            (3, 5)
        """
        return tuple(sorted(violation.rule for violation in self.violations))

    @property
    def expected(self) -> str:
        """
        Description:
        Werdykt, którego wymaga wpis: zablokować trzeba wiadomość, która łamie choć jedną regułę.

        Example args:
            (brak)

        Example result:
            "block"
        """
        return "block" if self.violations else "pass"

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa wpisu w raporcie: zgłoszenie z numerem komentarza, warstwa, łamane reguły i dopisek
        przy wpisie wątpliwym.

        Example args:
            (brak)

        Example result:
            "23921/2 (keywords, reguły 3, 6, wątpliwy)"
        """
        rules    = "poprawna"
        doubtful = ", wątpliwy" if self.doubtful else ""

        # Łamane reguły zamiast „poprawna”: po nich czyta się raport przepuszczeń.
        if self.violations:
            rules = f"reguły {', '.join(map(str, self.broken_rules))}"

        return f"{self.ticket_id}/{self.comment} ({self.stratum}, {rules}{doubtful})"
