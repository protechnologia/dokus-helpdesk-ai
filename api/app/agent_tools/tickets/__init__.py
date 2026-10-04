"""
Description:
Narzędzia agenta na zgłoszeniach historycznych. Oba są źródłami wiedzy, ale oddają inną postać
zgłoszenia: wyszukiwanie po znaczeniu — kartę z bazy wektorowej, wyszukiwanie tekstowe —
oryginalny wątek po anonimizacji z Postgresa.

| co                     | co zawiera                                                    |
|------------------------|---------------------------------------------------------------|
| `base.py`              | karta i wątek zgłoszenia w tekście dla modelu                 |
| `find_tickets_vector/` | karty znalezione po znaczeniu (embedder i Qdrant)             |
| `find_tickets_text/`   | wątki znalezione po dosłownym brzmieniu i słowach (Postgres)  |

Narzędzie importuje się z jego pakietu
(`from app.agent_tools.tickets.find_tickets_vector import FindTicketsVectorTool`), nie stąd.
"""
