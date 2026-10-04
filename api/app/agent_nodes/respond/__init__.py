"""
Description:
Węzeł `respond`: waliduje argumenty wywołania `respond_<graf>` do modelu wyjścia grafu (Verdict,
propozycja, karta zgłoszenia, tekst) — błąd wraca do modelu jako wiadomość `tool`, z jednym
retry — i egzekwuje `requires_hits`: graf, który wymaga źródeł, bez źródeł nie oddaje propozycji
(zasada 9).

Status: atrapa (`FakeRespondNode`); właściwy węzeł w p. 11 (CLAUDE.md -> „Plan").
"""

from app.agent_nodes.respond.fake import FakeRespondNode

__all__ = [
    "FakeRespondNode",
]
