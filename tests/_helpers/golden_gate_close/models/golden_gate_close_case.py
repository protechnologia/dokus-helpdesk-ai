import dataclasses


@dataclasses.dataclass(frozen=True)
class GoldenGateCloseCase:
    """Zamknięcie z zestawu bramki zamknięcia (`gate-close.json`): skąd wzięte, ile komentarzy
    widzi bramka i dwie etykiety, po jednej na regułę zamknięcia."""

    ticket_id:         str   # np. "33605"
    stratum:           str   # warstwa doboru: "longest", "mail", "rejected" albo "random"
    comments_at_close: int   # ile komentarzy stało w wątku w chwili zamknięcia
    digest:            str   # skrót uciętego wątku; pilnuje, że etykiety opisują ten tekst
    kind:              str   # "sprawa" albo "powiadomienie"; powiadomienia liczy się osobno
    problem_visible:   bool  # reguła 1: z treści wynika, co było problemem
    problem_reason:    str   # jednym zdaniem, co o tym przesądziło
    action_visible:    bool  # reguła 2: z treści wynika, co zrobiono, żeby problem rozwiązać
    action_reason:     str   # jednym zdaniem, co o tym przesądziło
    doubtful:          bool  # przypadek graniczny: oceniający nie był pewny którejś etykiety
