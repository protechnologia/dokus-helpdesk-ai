"""
Description:
Narzędzia agenta na zgłoszeniach historycznych. Oba są źródłami wiedzy i oba oddają te same
sparsowane zgłoszenia, od razu w całości — różni je droga wyszukania.

| co                     | co zawiera                                                    |
|------------------------|---------------------------------------------------------------|
| `base.py`              | rekord zgłoszenia w tekście dla modelu, ten sam w obu drogach |
| `find_tickets_vector/` | wyszukiwanie po znaczeniu (embedder i Qdrant)                 |
| `find_tickets_text/`   | wyszukiwanie po dosłownym brzmieniu i po słowach (Postgres)   |

Narzędzie importuje się z jego pakietu
(`from app.tools.tickets.find_tickets_vector import FindTicketsVectorTool`), nie stąd.
"""
