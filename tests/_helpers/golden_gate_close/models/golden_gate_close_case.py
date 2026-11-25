import dataclasses

from tests._helpers.golden_gate_close.constants import GROUP_LABELS


@dataclasses.dataclass(frozen=True)
class GoldenGateCloseCase:
    """Zamknięcie z zestawu bramki zamknięcia (`gate-close.json`): skąd wzięte, ile komentarzy
    widzi bramka i dwie etykiety, po jednej na regułę zamknięcia."""

    ticket_id:         str   # np. "33605"
    stratum:           str   # warstwa doboru: "longest", "mail", "rejected" albo "random"
    comments_at_close: int   # ile komentarzy stało w wątku w chwili zamknięcia
    digest:            str   # skrót uciętego wątku; pilnuje, że etykiety opisują ten tekst
    kind:              str   # "sprawa" albo "powiadomienie"; powiadomienia liczy się osobno
    problem_visible:   bool  # z treści wynika problem (reguły 1 i 2)
    problem_reason:    str   # jednym zdaniem, co o tym przesądziło
    action_visible:    bool  # z treści wynika rozwiązanie (reguły 1 i 3–6)
    action_reason:     str   # jednym zdaniem, co o tym przesądziło
    doubtful:          bool  # przypadek graniczny: oceniający nie był pewny którejś etykiety

    @property
    def group(self) -> str:
        """
        Description:
        Grupa wpisu: powiadomienie albo sprawa według tego, czego z niej nie widać. Powiadomienie
        idzie do własnej grupy bez patrzenia na reguły, bo bramka ma je zablokować zawsze
        (GAT-001).

        Example args:
            (brak)

        Example result:
            "no_solution"
        """
        # --- powiadomienie: blokada niezależnie od reguł ---
        if self.kind == "powiadomienie":
            return "notice"

        # --- sprawa, z której widać problem i rozwiązanie ---
        if self.problem_visible and self.action_visible:
            return "pass"

        # --- widać, co zrobiono, ale nie, co było problemem ---
        if self.action_visible:
            return "no_problem"

        # --- widać problem, ale nie, co zrobiono ---
        if self.problem_visible:
            return "no_solution"

        return "neither"

    @property
    def expected(self) -> str:
        """
        Description:
        Werdykt, którego wymaga wpis: przejść ma tylko sprawa, z której widać problem i rozwiązanie.

        Example args:
            (brak)

        Example result:
            "block"
        """
        return "pass" if self.group == "pass" else "block"

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa wpisu w raporcie: numer zgłoszenia, warstwa, grupa i dopisek przy wpisie wątpliwym.

        Example args:
            (brak)

        Example result:
            "33605 (random, nie widać rozwiązania, wątpliwy)"
        """
        doubtful = ", wątpliwy" if self.doubtful else ""

        return f"{self.ticket_id} ({self.stratum}, {GROUP_LABELS[self.group]}{doubtful})"
