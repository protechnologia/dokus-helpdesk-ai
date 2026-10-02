"""
Description:
Węzeł `respond`: zamienia ostatnią odpowiedź modelu na model wyjścia grafu (Verdict,
propozycja, karta zgłoszenia, tekst) — z jednym retry przy błędzie walidacji — i egzekwuje
`requires_hits`: graf, który wymaga źródeł, bez źródeł nie oddaje propozycji (zasada 9).

Status: atrapa (`FakeRespond`); właściwy węzeł w p. 11 (CLAUDE.md -> „Plan i TODO").
"""

from app.nodes.respond.fake import FakeRespond

__all__ = [
    "FakeRespond",
]
