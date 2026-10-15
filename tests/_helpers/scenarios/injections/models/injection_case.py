import dataclasses
from collections.abc import Mapping
from typing import Any

from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.db_postgres.row.tickets import TicketRow


@dataclasses.dataclass(frozen=True)
class InjectionCase:
    """Jedna sprawa do przepuszczenia przez graf: kontrolna albo z atakiem."""

    label:    str                     # np. "h01 polecenie wprost w komentarzu klienta"
    control:  bool                    # sprawa kontrolna, czyli wejście bez ataku
    text:     str                     # wejście grafu, np. "ZGŁOSZENIE 90101…\n\nKOMENTARZ 4…"
    rules:    tuple[str, ...] | None  # reguły klienta; None — graf bez reguł
    markers:  tuple[str, ...]         # znaczniki do szukania, np. ("KANAREK-4417",)
    expected: Mapping[str, Any]       # np. {"verdict": "block"}; puste — wyniku nie porównuje się

    # Materiał atrap z doklejonym atakiem; None — materiał wbudowany, bez ataku.
    cards:   tuple[ParsedTicket, ...] | None = None
    threads: tuple[TicketRow, ...] | None    = None
