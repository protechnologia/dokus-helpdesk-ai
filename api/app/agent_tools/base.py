from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from app.agent_tools.models import SourceRef
from app.core_util.markdown import read_document

# Opis narzędzia dla modelu leży w katalogu narzędzia pod tą nazwą.
DESCRIPTION_FILE = "description.md"


def read_description(
    module_file: str,  # np. "/code/app/agent_tools/tickets/find_tickets_vector/base.py"
) -> str:
    """
    Description:
    Czyta opis narzędzia dla modelu z `description.md` leżącego obok podanego modułu, bez
    komentarzy redakcyjnych. Woła ją klasa wspólna narzędzia i atrapy, więc oba przedstawiają się
    modelowi tym samym tekstem.

    Example args:
        module_file="/code/app/agent_tools/tickets/find_tickets_vector/base.py"

    Example result:
        "Szuka w bazie historycznych zgłoszeń spraw podobnych do opisanego problemu, od…"

    Raises:
        FileNotFoundError: narzędzie nie ma opisu
    """
    return read_document(Path(module_file).parent / DESCRIPTION_FILE).rstrip()


class KnowledgeSource(ABC):
    """
    Description:
    Narzędzie, które agent woła, żeby pobrać materiał, z którego może powstać odpowiedź.

    Do czego:
    Pierwszy z dwóch rodzajów narzędzi agenta (drugi to `AuxiliaryTool`). Wyróżnia go to, że jego
    wyniki mogą stać się ŹRÓDŁAMI odpowiedzi — które, mówi `cite()`. Nowe źródło to nowy katalog
    w folderze swojego materiału (`app/agent_tools/tickets/`, `app/agent_tools/docs/`):
    implementacja, jej atrapa i `models.py` z własnym zapytaniem, znalezionym elementem
    i wynikiem. Grafy sięgają po źródło przez własny adapter, więc ten plik nie wie nic
    o LangGraphie ani LangChainie.

    Flow:
        1. Agent woła `search()` z argumentami zgodnymi z `query_model`. Jak źródło szuka, to
           jego sprawa: po znaczeniu (`find_tickets_vector`), po dosłownym brzmieniu
           (`find_tickets_text`) albo po identyfikatorach (`read_docs`).
        2. `render_for_model()` zamienia wynik na tekst, który czyta model — to własna
           serializacja źródła, bo tylko ono wie, które jego pola się liczą i jak je pokazać.
        3. `cite()` zamienia ten sam wynik na źródła, które może wnieść do odpowiedzi. W adapterze
           grafu te dwie rzeczy stają się treścią i artefaktem narzędzia.

    Każda implementacja musi być tylko do odczytu: prompt wstrzyknięty przez treść zgłoszenia może
    co najwyżej skierować agenta do nietrafionego materiału, nigdy zmienić zawartości indeksu.
    """

    # Nazwa narzędzia — pod nią woła je model.
    name: ClassVar[str]

    # Opis dla modelu: jak pytać narzędzie i co ono oddaje. Ten sam w każdym grafie.
    description: ClassVar[str]

    # Nazwa MATERIAŁU („tickets", „docs"); trafia do `SourceRef.source`. Narzędzia szukające w tym
    # samym materiale różnymi drogami mają ją wspólną, więc to samo zgłoszenie jest źródłem raz.
    source: ClassVar[str]

    # Klasa zapytania: adapter robi z niej schemat argumentów dla modelu i nią je waliduje.
    query_model: ClassVar[type[BaseModel]]

    @abstractmethod
    async def search(
        self,
        query: BaseModel,  # np. FindTicketsVectorQuery(problem="Wysyłka ePUAP z błędem", …)
    ) -> BaseModel:
        """
        Description:
        Znajduje materiał odpowiadający zapytaniu, od najlepszego, już przycięty progiem albo
        limitem źródła. Przyjmuje obiekt klasy `query_model` i zwraca własny wynik źródła.

        Example args:
            query=FindTicketsVectorQuery(problem="Wysyłka przez ePUAP kończy się błędem",
                                         symptoms="Po kliknięciu Wyślij komunikat o braku sieci")

        Example result:
            FindTicketsVectorResult(items=[FoundTicket(score=0.87, ticket=ParsedTicket(…))],
                                    dropped_below_threshold=2)
        """

    @abstractmethod
    def render_for_model(
        self,
        result: BaseModel,  # np. FindTicketsVectorResult(items=[…])
    ) -> str:
        """
        Description:
        Zamienia wynik wyszukiwania na tekst, który model czyta zamiast odpowiedzi narzędzia.
        Strukturalny wynik nigdy nie trafia do modelu wprost — model widzi wyłącznie ten tekst.

        Example args:
            result=FindTicketsVectorResult(items=[FoundTicket(…)], dropped_below_threshold=2)

        Example result:
            Znalezione zgłoszenia: 1 (odcięte progiem: 2)

            [33644] 2026-03-14 · podobieństwo 0.87
            …
        """

    @abstractmethod
    def cite(
        self,
        result: BaseModel,  # np. FindTicketsVectorResult(items=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Wymienia, co z wyniku wyszukiwania odpowiedź może zacytować — jeden wpis na każdy element,
        który model zobaczył w `render_for_model()`, z tytułem, po którym człowiek rozpozna
        źródło. Lista źródeł powstaje stąd, nigdy z tego, co model deklaruje, że wykorzystał.

        Example args:
            result=FindTicketsVectorResult(items=[FoundTicket(score=0.87, ticket=ParsedTicket(…))])

        Example result:
            [SourceRef(source="tickets", item_id="33644", title="Wysyłka przez ePUAP…",
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
    Narzędzie, które agent woła po coś innego niż materiał do cytowania: spis treści
    dokumentacji i jej wyszukiwarki, a później notatki agenta.

    Do czego:
    Drugi rodzaj narzędzia agenta, oddzielony od `KnowledgeSource` z samej konstrukcji: zwraca
    zwykły tekst i nie ma `cite()`, więc jego wynik nigdy nie trafi na listę źródeł odpowiedzi.
    Tylko po to ten rodzaj istnieje. Wiersz spisu treści mówi, GDZIE jest instrukcja, a nie co
    w niej stoi — odpowiedź oparta na samym wierszu nie ma źródła, i kontrakt sprawia, że nie da
    się go jej przypisać przez pomyłkę. Źródłem jest dopiero odczytana sekcja (`read_docs`).

    Flow:
        1. Agent woła narzędzie z argumentami zgodnymi z `args_model`.
        2. `run()` zwraca tekst, który model czyta zamiast odpowiedzi narzędzia.
    """

    # Nazwa narzędzia.
    name: ClassVar[str]

    # Opis dla modelu — ta sama rola co w KnowledgeSource.
    description: ClassVar[str]

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


# Każde narzędzie, które może dostać agent — tym typem przyjmuje je kod składający grafy.
AgentTool = KnowledgeSource | AuxiliaryTool
