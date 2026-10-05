"""
Description:
Prawdziwe narzędzie `find_tickets_text`: znajduje w Postgresie zgłoszenia po dosłownym brzmieniu
i po słowach kluczowych — w oryginalnych wątkach, po anonimizacji — i oddaje ich numery
z informacją, czym każde znaleziono. Nie woła embeddera ani LLM-a — tylko tabelę zgłoszeń.

    `exact` → podciąg ──────────────────────┐
                                            ├→ jedna lista, każdy numer raz → limit → numery
    `words` → słowa przez polski słownik ───┘

Przed — zapytanie agenta:

    FindTicketsTextQuery(exact="Nie udało się skomunikować z serwerem", words="załącznik limit")

Po — wynik `find()` (limit 5; frazę mają dwa wątki, oba słowa — pierwszy z nich i jeszcze jeden):

    FindTicketsTextResult(
        tickets = [
            MatchedTicket(ticket_id="90011", matched_by="exact"),
            MatchedTicket(ticket_id="90012", matched_by="exact"),
            MatchedTicket(ticket_id="90003", matched_by="words"),
        ],
        omitted_over_limit = 0,
    )

Co się dzieje po drodze:

1. Fraza z `exact` jest szukana dosłownie, bez względu na wielkość liter i na to, jak wątek
   złamano między liniami; `words` — przez słownik, w dowolnej odmianie i kolejności.
2. Wyniki łączą się w jedną listę: najpierw zgłoszenia znalezione frazą, potem słowami.
   Zgłoszenie znalezione obiema drogami stoi raz, jako znalezione frazą.
3. Lista jest cięta do `RAG_TOP_K`; reszta jest policzona w `omitted_over_limit`.

O czym pamiętać przy zmianach:

- Pola szukają niezależnie i wyniki się sumują. Zgłoszenie nie musi pasować do obu.
- `exact` to jedna fraza, nie lista: przy kilku frazach wynik nie mówiłby, która trafiła.
  Kilka tropów — kod z ekranu, kod z logów, komunikat — to kilka wywołań.
- Fraza idzie przez podciąg, nie przez słownik: parser pełnotekstowy skleja kod z interpunkcją
  w jeden token, więc fragmentu kodu („00942" z „ORA-00942") słowami nie znajdzie.
- Wynik to same numery, więc z tabeli nic nie jest czytane: wątek daje `read_tickets_thread`,
  kartę `read_tickets_card`, i tylko one cytują.
- Zgłoszenia znalezione frazą stoją w kolejności numerów czytanych jako tekst („10718" przed
  „6773"), bo dopasowanie dosłowne nie ma stopnia. Przy trafieniach ponad limit to ona
  rozstrzyga, które numery model zobaczy.
- Ile zwrócić, ustawia konfiguracja, nie agent — zapytanie niesie tylko to, czego szukać.
"""

import logging

from app.agent_tools.base import label_matches
from app.agent_tools.tickets.find_tickets_text.base import FindTicketsTextToolBase
from app.agent_tools.tickets.find_tickets_text.models import (
    FindTicketsTextQuery,
    FindTicketsTextResult,
    MatchedTicket,
)
from app.db_postgres import TicketsTable

logger = logging.getLogger(__name__)


class FindTicketsTextTool(FindTicketsTextToolBase):
    """
    Description:
    `find_tickets_text` na prawdziwym indeksie: tabela zgłoszeń w Postgresie znajduje wątki po
    frazie i po słowach, a narzędzie łączy wyniki, tnie je limitem i oddaje numery zgłoszeń.

    Do czego:
    Wyszukiwanie zgłoszeń po dosłownym brzmieniu w grafach `search`, `suggest_questions`
    i `suggest_solution` — dla kodu błędu albo komunikatu, którego karta zgłoszenia nie
    zachowała. Tylko do odczytu: nic tu nie zapisuje do indeksu.

    Flow:
        1. `find()` pyta tabelę o frazę z `exact` i o `words`; dostaje numery zgłoszeń.
        2. `label_matches()` łączy je w jedną listę z etykietami.
        3. Lista jest cięta do `limit`, a reszta policzona.
        4. `run()` z klasy bazowej robi z wyniku JSON dla modelu.
    """

    def __init__(
        self,
        tickets: TicketsTable,  # np. TicketsTable(PostgresClient(host="postgres", …))
        limit:   int,           # np. 5 — RAG_TOP_K
    ):
        """
        Description:
        Spina narzędzie z tabelą zgłoszeń i z limitem długości wyniku. Tabela jest wstrzykiwana,
        nie budowana tutaj (zasada 4).

        Example args:
            tickets=TicketsTable(PostgresClient(host="postgres", port=5432, database="helpdesk", …))
            limit=5

        Example result:
            FindTicketsTextTool gotowe do wyszukiwania w tabeli `tickets_text`
        """
        self._tickets = tickets
        self._limit   = limit

    async def find(
        self,
        query: FindTicketsTextQuery,  # np. FindTicketsTextQuery(exact="SQLSTATE[23000]")
    ) -> FindTicketsTextResult:
        """
        Description:
        Znajduje zgłoszenia, których wątek zawiera frazę z `exact` albo wszystkie słowa z `words`,
        znalezione frazą najpierw, przycięte limitem.

        Example args:
            query=FindTicketsTextQuery(exact="Nie udało się skomunikować z serwerem")

        Example result:
            FindTicketsTextResult(tickets=[MatchedTicket(ticket_id="90011", matched_by="exact"),
                                           MatchedTicket(ticket_id="90012", matched_by="exact")],
                                  omitted_over_limit=0)

        Raises:
            DbPostgresError: Postgres jest nieosiągalny albo odpowiedział błędem
        """
        # --- fraza: dosłownie; słowa: przez słownik, najlepiej dopasowane pierwsze ---
        exact_ids = await self._tickets.substring(query.exact) if query.exact else []
        words_ids = await self._tickets.words(query.words) if query.words else []

        # --- jedna lista, cięta limitem; resztę liczymy, zamiast gubić ---
        matched = label_matches(exact_ids, words_ids)
        kept    = list(matched)[: self._limit]
        omitted = len(matched) - len(kept)

        # Same liczby: zapytanie agenta niesie treść zgłoszenia.
        logger.info(
            "find_tickets_text exact=%s words=%s matched=%d omitted=%d",
            bool(query.exact),
            bool(query.words),
            len(matched),
            omitted,
        )

        result = FindTicketsTextResult(
            tickets = [
                MatchedTicket(ticket_id=ticket_id, matched_by=matched[ticket_id])
                for ticket_id in kept
            ],
            omitted_over_limit = omitted,
        )

        return result

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenie z Postgresem. Sprzątający woła tylko to i nie musi wiedzieć, z czego
        narzędzie jest zbudowane.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._tickets.aclose()
