from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field


class SourceRef(BaseModel):
    """
    Description:
    Jeden wpis na liście źródeł, które cytuje odpowiedź: które narzędzie co znalazło, z jakim
    podobieństwem i kiedy materiał powstał.

    Do czego:
    JEDYNY model wspólny dla wszystkich narzędzi agenta. Każde narzędzie trzyma swoje zapytanie,
    znalezione elementy i wynik w `models.py` własnego katalogu, bez wspólnej bazy; od dowolnego
    narzędzia reszta systemu potrzebuje wyłącznie tego zapisu — dość, żeby zacytować źródło, nic
    z jego treści. Treść trafia do modelu jako tekst (`render_for_model`), a lista źródeł powstaje
    z tych zapisów (`cite`), nigdy z tego, co model deklaruje, że przeczytał (zasada 9).

    Flow:
        1. `cite()` źródła wiedzy zamienia jego wynik wyszukiwania na listę takich zapisów.
        2. Węzeł narzędzi zbiera je ze wszystkich wywołań, bez powtórzeń według `key`.
        3. Węzeł odpowiedzi zwraca je jako listę źródeł odpowiedzi.

    Konkretny zapis, a nie baza, po której dziedziczą elementy narzędzi: kod wspólny ma cytować,
    a nie czytać treść — a lista typowana klasą bazową i tak serializowałaby tylko pola bazowe
    (`model_dump()` po cichu gubi resztę, sprawdzone na Pydanticu 2.10).

    `title` to jedna linia, po której człowiek rozpozna źródło — `problem` zgłoszenia, nazwa
    i wersja dokumentu — więc listę źródeł da się czytać bez otwierania czegokolwiek. Przy
    zgłoszeniu wystarczyłoby samo id (helpdesk otworzy je we własnej bazie), ale nie przy
    fragmencie dokumentacji, którego helpdesk nie ma. Pełnej treści świadomie tu nie ma: model
    przeczytał ją już jako tekst, a jej kopia niosłaby każde źródło dwa razy przez stan grafu.
    `date` jest zawsze, bo od niej zależą dezaktualizacja, sprzeczności i sezonowość (CLAUDE.md ->
    „Twarde reguły promptu generacji").
    """

    model_config = ConfigDict(extra="forbid")

    source:  str         = Field(min_length=1, examples=["find_tickets"])
    item_id: str         = Field(min_length=1, examples=["33644"])
    title:   str         = Field(min_length=1, examples=["Wysyłka przez ePUAP kończy się błędem"])
    score:   float       = Field(examples=[0.87])
    date:    Date | None = Field(default=None, examples=["2026-03-14"])

    @property
    def key(self) -> str:
        """
        Description:
        Tożsamość źródła we wszystkich narzędziach. Id są unikalne tylko w obrębie jednego
        narzędzia — zgłoszenie i fragment dokumentacji mogą oba mieć „33644" — więc usuwanie
        powtórzeń w źródłach jednej odpowiedzi po samym `item_id` po cichu scaliłoby dwa
        niezwiązane materiały.

        Example args:
            (brak)

        Example result:
            "find_tickets:33644"
        """
        return f"{self.source}:{self.item_id}"
