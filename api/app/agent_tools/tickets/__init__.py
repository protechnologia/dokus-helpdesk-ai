"""
Description:
Narzędzia agenta na zgłoszeniach historycznych. Idą dwustopniowo, jak dokumentacja: oba
wyszukiwania oddają numery zgłoszeń, a treść dają dopiero odczyty — i tylko one cytują.
Zgłoszenie ma dwie postaci: kartę, czyli streszczenie w polach, i oryginalny wątek po
anonimizacji. Którą przeczytać, wybiera agent, niezależnie od tego, jak zgłoszenie znalazł.

| co                     | co zawiera                                                       |
|------------------------|------------------------------------------------------------------|
| `fake_tickets.py`      | zmyślone zgłoszenia, na których stoją atrapy całej czwórki       |
| `find_tickets_vector/` | wyszukiwanie po znaczeniu: numery z podobieństwem                |
| `find_tickets_text/`   | wyszukiwanie po dosłownym brzmieniu: numery ze sposobem trafienia |
| `read_tickets_card/`   | karty zgłoszeń po numerach                                       |
| `read_tickets_thread/` | oryginalne wątki zgłoszeń po numerach                            |

Każde narzędzie stoi na jednej bazie: wyszukiwanie po znaczeniu i karty na Qdrancie,
wyszukiwanie tekstowe i wątki na Postgresie. Model o bazach nie wie nic — zna kartę jako
streszczenie i wątek jako oryginalną treść z komentarzami.

Narzędzie importuje się z jego pakietu
(`from app.agent_tools.tickets.find_tickets_vector import FindTicketsVectorTool`), nie stąd.
"""
