from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenTextQuery:
    """Zapytanie zestawu tekstowego w polach `find_tickets_text`, z celem albo bez celu."""

    ticket_id:  str | None  # zgłoszenie-cel; `None` przy zapytaniu bez celu (dystraktorze)
    kind:       str         # warstwa: „kod”, „komunikat_ekran”, „komunikat_log” albo „nazwa”
    difficulty: str         # „typowe” albo „trudne” (sprawdza znaną słabość narzędzia)
    exact:      str | None  # fraza szukana dosłownie
    words:      str | None  # słowa szukane przez słownik, w innej odmianie niż w wątku
    note:       str | None  # przy trudnym: jaką słabość sprawdza
