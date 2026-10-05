from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from app.agent_tools.models import MatchKind, SourceRef
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


def result_as_json(
    result:  BaseModel,           # np. FindTicketsVectorResult(tickets=[FoundTicket(…)])
    exclude: dict | None = None,  # np. {"cards": {"__all__": {"resolution_vocabulary_version"}}}
) -> str:
    """
    Description:
    Tekst, który model czyta jako odpowiedź narzędzia: wynik narzędzia zapisany jako JSON. Jedno
    miejsce dla wszystkich narzędzi, więc każde odpowiada w tym samym formacie, a identyfikatory
    wracają w kształcie, w jakim model poda je następnemu narzędziu.

    Treść pisana przez klienta (wątek zgłoszenia) siedzi w polu tekstowym i z niego nie wyjdzie:
    nie może udawać końca wyniku ani kolejnego pola. Polskie litery zostają bez zmian.
    `exclude` wycina pola, które są w wyniku dla nas, a nie dla modelu.

    Example args:
        result=FindTicketsVectorResult(tickets=[FoundTicket(ticket_id="90001", score=0.91)])
        exclude=None

    Example result:
        {
          "tickets": [
            {
              "ticket_id": "90001",
              "score": 0.91
            }
          ],
          "dropped_below_threshold": 0
        }
    """
    return result.model_dump_json(indent=2, exclude=exclude)


def label_matches(
    exact_ids: Iterable[str],  # np. ["90011"] — znalezione frazą z `exact`
    words_ids: Iterable[str],  # np. ["90012", "90011"] — znalezione słowami z `words`
) -> dict[str, MatchKind]:
    """
    Description:
    Łączy wyniki obu dróg wyszukiwania tekstowego w jedną listę z etykietami: najpierw to, co
    znalazła fraza, potem to, co znalazły słowa. Identyfikator znaleziony obiema drogami stoi
    raz, z etykietą `exact` — trafienie po przepisanej frazie mówi więcej niż po słowach
    kluczowych. Wspólne dla `find_tickets_text` i `find_docs_text`.

    Example args:
        exact_ids=["90011"]
        words_ids=["90012", "90011"]

    Example result:
        {"90011": "exact", "90012": "words"}
    """
    matched: dict[str, MatchKind] = {}

    for item_id in exact_ids:
        matched.setdefault(item_id, "exact")

    for item_id in words_ids:
        matched.setdefault(item_id, "words")

    return matched


class KnowledgeSource(ABC):
    """
    Description:
    Narzędzie, które agent woła, żeby przeczytać materiał, z którego może powstać odpowiedź.

    Do czego:
    Pierwszy z dwóch rodzajów narzędzi agenta (drugi to `AuxiliaryTool`). Wyróżnia go to, że jego
    wyniki stają się ŹRÓDŁAMI odpowiedzi — które, mówi `cite()`. Źródłami są wyłącznie odczyty
    (`read_tickets_card`, `read_tickets_thread`, `read_docs`): na listę źródeł trafia to, co model
    przeczytał, a nie to, co tylko znalazł. Nowe źródło to nowy katalog w folderze swojego
    materiału (`app/agent_tools/tickets/`, `app/agent_tools/docs/`): implementacja, jej atrapa
    i `models.py` z własnym zapytaniem i wynikiem. Grafy sięgają po źródło przez własny adapter,
    więc ten plik nie wie nic o LangGraphie ani LangChainie.

    Flow:
        1. Agent woła `search()` z argumentami zgodnymi z `query_model` — identyfikatorami, które
           dostał od wyszukiwania albo ze spisu treści.
        2. `render_for_model()` zamienia wynik na tekst, który czyta model: JSON wyniku.
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
        query: BaseModel,  # np. ReadTicketsCardQuery(ticket_ids=["33644"])
    ) -> BaseModel:
        """
        Description:
        Pobiera materiał wskazany w zapytaniu. Przyjmuje obiekt klasy `query_model` i zwraca
        własny wynik źródła.

        Example args:
            query=ReadTicketsCardQuery(ticket_ids=["33644"])

        Example result:
            ReadTicketsCardResult(cards=[ParsedTicket(ticket_id="33644", …)], without_card=[])
        """

    def render_for_model(
        self,
        result: BaseModel,  # np. ReadTicketsCardResult(cards=[…])
    ) -> str:
        """
        Description:
        Zamienia wynik na tekst, który model czyta jako odpowiedź narzędzia: JSON wyniku. Źródło
        nadpisuje tę metodę tylko wtedy, gdy część wyniku nie jest dla modelu.

        Example args:
            result=ReadTicketsCardResult(cards=[ParsedTicket(ticket_id="33644", …)])

        Example result:
            {"cards": [{"ticket_id": "33644", "problem": "…", …}], "without_card": []}
        """
        return result_as_json(result)

    @abstractmethod
    def cite(
        self,
        result: BaseModel,  # np. ReadTicketsCardResult(cards=[…])
    ) -> list[SourceRef]:
        """
        Description:
        Wymienia, co z wyniku odpowiedź może zacytować — jeden wpis na każdy element, który
        model zobaczył w `render_for_model()`, z tytułem, po którym człowiek rozpozna źródło.
        Lista źródeł powstaje stąd, nigdy z tego, co model deklaruje, że wykorzystał.

        Example args:
            result=ReadTicketsCardResult(cards=[ParsedTicket(ticket_id="33644", …)])

        Example result:
            [SourceRef(source="tickets", item_id="33644", title="Wysyłka przez ePUAP…",
                       date=date(2026, 3, 14))]
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
    Narzędzie, które agent woła po coś innego niż materiał do cytowania: wyszukiwarki zgłoszeń
    i dokumentacji, spis treści dokumentacji, a później notatki agenta.

    Do czego:
    Drugi rodzaj narzędzia agenta, oddzielony od `KnowledgeSource` z samej konstrukcji: zwraca
    sam tekst i nie ma `cite()`, więc jego wynik nigdy nie trafi na listę źródeł odpowiedzi.
    Tylko po to ten rodzaj istnieje. Wyszukiwanie mówi, GDZIE jest materiał — numer zgłoszenia,
    identyfikator sekcji — a nie co w nim stoi. Odpowiedź oparta na samym wyniku wyszukiwania
    nie ma źródła, i kontrakt sprawia, że nie da się go jej przypisać przez pomyłkę. Źródłem
    jest dopiero to, co model odczytał.

    Flow:
        1. Agent woła narzędzie z argumentami zgodnymi z `args_model`.
        2. `run()` zwraca tekst, który model czyta jako odpowiedź narzędzia — JSON wyniku
           (`result_as_json()`).
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
            args=FindTicketsVectorQuery(problem="Wysyłka ePUAP z błędem", symptoms="…")

        Example result:
            {"tickets": [{"ticket_id": "33644", "score": 0.87}], "dropped_below_threshold": 2}
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
