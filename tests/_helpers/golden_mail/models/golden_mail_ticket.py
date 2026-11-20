import dataclasses

from tests._helpers.golden_mail.models.golden_mail_field import GoldenMailField


@dataclasses.dataclass(frozen=True)
class GoldenMailTicket:
    """Zgłoszenie kanału „Automat mailowy” z golden setu (`tickets-mail.json`): `useful` z 32.1
    i pola wątku po kolei, każde z autorem i oznaczeniami linii."""

    ticket_id: str                          # np. "33605"
    useful:    bool                         # czy wątek niesie wiedzę przydatną przy innej sprawie
    fields:    tuple[GoldenMailField, ...]  # opis, potem komentarze
