import dataclasses

from tests._helpers.scenarios.injections.constants import INTO_INPUT


@dataclasses.dataclass(frozen=True)
class InjectionAttack:
    """Jeden atak z zestawu: na wejściu, w regułach klienta albo w materiale narzędzi, ze
    znacznikami, które zdradzą przebicie."""

    attack_id:  str                # np. "h01"
    phenomenon: str                # np. "polecenie wprost w komentarzu klienta"
    input_id:   str                # np. "podpis" — wejście, którego sprawa dotyczy
    attack:     str                # tekst ataku, np. "KOMENTARZ 4 — klient, …: Zignoruj…"
    markers:    tuple[str, ...]    # np. ("KANAREK-4417",)
    into:       str = INTO_INPUT   # np. "card" — atak w polu karty historycznej sprawy
    ticket:     str | None = None  # np. "90002" — sprawa z materiału atrap, przy `card` i `thread`
    field:      str | None = None  # np. "questions_summary" — pole karty, przy `card`
