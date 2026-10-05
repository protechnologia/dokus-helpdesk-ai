from datetime import date as Date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# --- wspólne dla obu wyszukiwań tekstowych (`find_tickets_text`, `find_docs_text`) ---

# Fraza szukana dosłownie ma co najmniej trzy znaki: krótsza trafia w przypadkowe miejsca (numer
# telefonu, data), a trafienie po „50" wygląda na trafienie, choć nim nie jest. Spacje z brzegów
# są najpierw obcinane i dopiero potem liczona jest długość: fraza z samych spacji spełniałaby
# wymóg trzech znaków, a pasuje do każdego tekstu, w którym jest spacja.
ExactText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3)]

# Czym coś znaleziono: dosłownym ciągiem albo słowami kluczowymi. Wartości to nazwy pól zapytania,
# którymi agent sam pytał.
MatchKind = Literal["exact", "words"]


class SourceRef(BaseModel):
    """
    Description:
    Jeden wpis na liście źródeł, które cytuje odpowiedź: z jakiego materiału pochodzi („tickets",
    „docs"), co to jest i kiedy powstało.

    Do czego:
    JEDYNY model wspólny dla wszystkich narzędzi agenta (obok stoją tylko dwa proste typy
    wyszukiwań tekstowych). Każde narzędzie trzyma swoje zapytanie i wynik w `models.py` własnego
    katalogu, bez wspólnej bazy; od narzędzia, które cytuje, reszta systemu potrzebuje wyłącznie
    tego zapisu — dość, żeby zacytować źródło, nic z jego treści. Treść trafia do modelu jako
    tekst (`render_for_model`), a lista źródeł powstaje z tych zapisów (`cite`), nigdy z tego,
    co model deklaruje, że przeczytał (zasada 9).

    Flow:
        1. `cite()` źródła wiedzy zamienia wynik odczytu na listę takich zapisów.
        2. Węzeł narzędzi zbiera je ze wszystkich wywołań, bez powtórzeń według `key`.
        3. Węzeł odpowiedzi zwraca je jako listę źródeł odpowiedzi.

    Konkretny zapis, a nie baza, po której dziedziczą elementy narzędzi: kod wspólny ma cytować,
    a nie czytać treść — a lista typowana klasą bazową i tak serializowałaby tylko pola bazowe
    (`model_dump()` po cichu gubi resztę, sprawdzone na Pydanticu 2.10).

    `title` to jedna linia, po której człowiek rozpozna źródło — `problem` karty, temat wątku,
    nazwa i wersja dokumentu — więc listę źródeł da się czytać bez otwierania czegokolwiek. Przy
    zgłoszeniu wystarczyłoby samo id (helpdesk otworzy je we własnej bazie), ale nie przy
    fragmencie dokumentacji, którego helpdesk nie ma. Pełnej treści świadomie tu nie ma: model
    przeczytał ją już jako tekst, a jej kopia niosłaby każde źródło dwa razy przez stan grafu.
    `date` jest zawsze, bo od niej zależą dezaktualizacja, sprzeczności i sezonowość (CLAUDE.md ->
    „Twarde reguły promptu generacji").

    Podobieństwa tu nie ma: źródłem jest to, co model odczytał po identyfikatorze, a odczyt nie
    zna podobieństwa. Widzi je tylko model, w wyniku wyszukiwania.
    """

    model_config = ConfigDict(extra="forbid")

    source:  str         = Field(min_length=1, examples=["tickets"])
    item_id: str         = Field(min_length=1, examples=["33644"])
    title:   str         = Field(min_length=1, examples=["Wysyłka przez ePUAP kończy się błędem"])
    date:    Date | None = Field(default=None, examples=["2026-03-14"])

    @property
    def key(self) -> str:
        """
        Description:
        Tożsamość źródła we wszystkich narzędziach. Id są unikalne tylko w obrębie jednego
        materiału — zgłoszenie i fragment dokumentacji mogą oba mieć „33644" — więc usuwanie
        powtórzeń w źródłach jednej odpowiedzi po samym `item_id` po cichu scaliłoby dwa
        niezwiązane materiały. `source` nazywa materiał, nie narzędzie: to samo zgłoszenie
        odczytane jako karta i jako wątek ma jeden klucz i trafia na listę raz.

        Example args:
            (brak)

        Example result:
            "tickets:33644"
        """
        return f"{self.source}:{self.item_id}"
