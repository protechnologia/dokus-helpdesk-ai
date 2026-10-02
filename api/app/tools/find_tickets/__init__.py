"""
Description:
Źródło wiedzy: historyczne zgłoszenia podobne do bieżącego.

Do czego:
Agent podaje zgłoszenie w kształcie korpusu (`problem` + `symptoms`), narzędzie składa z tego tekst
do embeddingu tak jak `ParsedTicket.embedding_text()`, zamienia go na wektor w trybie QUERY,
dopasowuje do wektorów `problem` i przycina progiem `RAG_SCORE_MIN`. Parsera nie woła — to
różnica wobec wyszukiwania z etapu 5 (`service/rag_searcher.py`), gdzie zgłoszenie parsował
osobny krok. Treścią każdego elementu jest sparsowane zgłoszenie z payloadu Qdranta, więc `cause`
i `solution` docierają do modelu jako pola, nigdy jako surowy mail.

Co model musi zobaczyć (CLAUDE.md -> „Plan i TODO", p. 18): rozłączne przyczyny wszystkich trafień
w jednym bloku PRZED rekordami, a przyczyny-sentinele („brak", „Brak ustalonej przyczyny…") jako
„(nie ustalono)" i nigdy liczone jako zgodność. Przyczyna utopiona wśród sześciu innych pól do
modelu nie dociera, a trzy puste przyczyny to nie trzy zgodne.

Status: tylko modele. `fake.py` powstaje w p. 2, `tool.py` w p. 9.
"""

from app.tools.find_tickets.models import FindTicketsQuery, FindTicketsResult, FoundTicket

__all__ = [
    "FindTicketsQuery",
    "FindTicketsResult",
    "FoundTicket",
]
