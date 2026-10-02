from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from app.tools.models import SourceRef


class KnowledgeSource(ABC):
    """
    Description:
    Narzędzie, które agent woła, żeby pobrać materiał, z którego może powstać odpowiedź.

    Do czego:
    Pierwszy z dwóch rodzajów narzędzi agenta (drugi to `AuxiliaryTool`). Wyróżnia go to, że jego
    wyniki mogą stać się ŹRÓDŁAMI odpowiedzi — które, mówi `cite()`. Nowe źródło to nowy katalog
    w `app/tools/`: implementacja, jej atrapa i `models.py` z własnym zapytaniem, znalezionym
    elementem i wynikiem. Grafy sięgają po źródło przez własny adapter, więc ten plik nie wie nic
    o LangGraphie ani LangChainie.

    Flow:
        1. Agent woła `search()` z argumentami zgodnymi z `query_model` — wyszukiwanie
           SEMANTYCZNE: zapytanie zamieniane jest na wektor i dopasowywane po podobieństwie,
           nigdy wyszukiwane po id.
        2. `render_for_model()` zamienia wynik na tekst, który czyta model — to własna
           serializacja źródła, bo tylko ono wie, które jego pola się liczą i jak je pokazać.
        3. `cite()` zamienia ten sam wynik na źródła, które może wnieść do odpowiedzi. W adapterze
           grafu te dwie rzeczy stają się treścią i artefaktem narzędzia.

    Bez odczytu po id: dziś nic nie potrzebuje znalezionego elementu ponownie po zakończeniu
    pętli. Odczyt wraca razem z krokiem human-in-the-loop (CLAUDE.md -> „Plan i TODO", p. 44).

    Każda implementacja musi być tylko do odczytu: prompt wstrzyknięty przez treść zgłoszenia może
    co najwyżej skierować agenta do nietrafionego materiału, nigdy zmienić zawartości indeksu.
    """

    # Nazwa narzędzia; trafia też do `SourceRef.source`.
    name: ClassVar[str]

    # Klasa zapytania: adapter robi z niej schemat argumentów dla modelu i nią je waliduje.
    query_model: ClassVar[type[BaseModel]]

    @abstractmethod
    async def search(
        self,
        query: BaseModel,  # np. FindTicketsQuery(problem="Wysyłka ePUAP kończy się błędem", …)
    ) -> BaseModel:
        """
        Description:
        Znajduje materiał podobny znaczeniowo do zapytania, od najlepszego, już przycięty progiem
        źródła. Przyjmuje obiekt klasy `query_model` i zwraca własny wynik źródła.

        Example args:
            query=FindTicketsQuery(problem="Wysyłka przez ePUAP kończy się błędem",
                                   symptoms="Po kliknięciu Wyślij komunikat o braku sieci")

        Example result:
            FindTicketsResult(items=[FoundTicket(score=0.87, ticket=ParsedTicket(…))],
                              dropped_below_threshold=2)
        """

    @abstractmethod
    def render_for_model(
        self,
        result: BaseModel,  # np. FindTicketsResult(items=[…])
    ) -> str:
        """
        Description:
        Zamienia wynik wyszukiwania na tekst, który model czyta zamiast odpowiedzi narzędzia.
        Strukturalny wynik nigdy nie trafia do modelu wprost — model widzi wyłącznie ten tekst.

        Example args:
            result=FindTicketsResult(items=[FoundTicket(…)], dropped_below_threshold=2)

        Example result:
            "Przyczyny w trafieniach:\\n- certyfikat bez uprawnienia…\\n\\nTrafienie 33644 …"
        """

    @abstractmethod
    def cite(
        self,
        result: BaseModel,  # np. FindTicketsResult(items=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Wymienia, co z wyniku wyszukiwania odpowiedź może zacytować — jeden wpis na każdy element,
        który model zobaczył w `render_for_model()`, z tytułem, po którym człowiek rozpozna
        źródło. Lista źródeł powstaje stąd, nigdy z tego, co model deklaruje, że wykorzystał.

        Example args:
            result=FindTicketsResult(items=[FoundTicket(score=0.87, ticket=ParsedTicket(…))])

        Example result:
            [SourceRef(source="find_tickets", item_id="33644", title="Wysyłka przez ePUAP…",
                       score=0.87, date=date(2026, 3, 14))]
        """

    async def aclose(self) -> None:
        """
        Description:
        Zwalnia to, co źródło trzyma otwarte. Domyślnie nic; źródło opakowujące klientów HTTP
        nadpisuje tę metodę, żeby sprzątający nie musiał wiedzieć, z czego źródło jest zbudowane.

        Example args:
            (brak)

        Example result:
            None
        """
        return None


class AuxiliaryTool(ABC):
    """
    Description:
    Narzędzie, które agent woła po coś innego niż materiał do cytowania — pierwszymi będą
    planowane notatki agenta.

    Do czego:
    Drugi rodzaj narzędzia agenta, oddzielony od `KnowledgeSource` z samej konstrukcji: zwraca
    zwykły tekst i nie ma `cite()`, więc jego wynik nigdy nie trafi na listę źródeł odpowiedzi.
    Tylko po to ten rodzaj istnieje — notatka, którą model napisał sam dla siebie, nie jest
    dowodem, a kontrakt sprawia, że nie da się jej za taki uznać przez pomyłkę.

    Flow:
        1. Agent woła narzędzie z argumentami zgodnymi z `args_model`.
        2. `run()` zwraca tekst, który model czyta zamiast odpowiedzi narzędzia.
    """

    # Nazwa narzędzia.
    name: ClassVar[str]

    # Klasa argumentów — ta sama rola co `query_model` w KnowledgeSource.
    args_model: ClassVar[type[BaseModel]]

    @abstractmethod
    async def run(
        self,
        args: BaseModel,  # np. obiekt klasy `args_model`
    ) -> str:
        """
        Description:
        Wykonuje działanie narzędzia i zwraca tekst, który czyta model.

        Example args:
            args=args_model(…)

        Example result:
            "Zapisano."
        """

    async def aclose(self) -> None:
        """
        Description:
        Zwalnia to, co narzędzie trzyma otwarte. Domyślnie nic.

        Example args:
            (brak)

        Example result:
            None
        """
        return None
