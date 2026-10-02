"""
Description:
Węzeł `respond`: waliduje argumenty wywołania `respond_<graf>` do modelu wyjścia grafu (Verdict,
propozycja, karta zgłoszenia, tekst) — błąd wraca do modelu jako wiadomość `tool`, z jednym
retry — i egzekwuje `requires_hits`: graf, który wymaga źródeł, bez źródeł nie oddaje propozycji
(zasada 9).

Status: atrapa (`FakeRespond`); właściwy węzeł w p. 11 (CLAUDE.md -> „Plan i TODO").
"""

from app.nodes.respond.fake import FakeRespond

__all__ = [
    "FakeRespond",
]
