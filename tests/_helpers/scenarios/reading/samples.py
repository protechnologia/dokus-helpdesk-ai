"""
Description:
Próbki do testów samego helpera czytania (`tests/unit/test_reading_report.py`): cztery sprawy,
wyniki grafów i tura modelu z wywołaniami narzędzi. Dzięki nim plik testu to same testy, a dane,
na których stoją asercje, leżą obok helpera, którego dotyczą.

| co                    | do czego                                                            |
|-----------------------|---------------------------------------------------------------------|
| `CASE_CAUSES`         | sprawa z trzema kartami do przeczytania i trzema przyczynami        |
| `CASE_EXCLUDED`       | ta sama sprawa z przyczyną, którą uwagi mają nazwać jako wykluczoną |
| `CASE_DOCS`           | sprawa z sekcją oczekiwaną i niepożądaną                            |
| `CASE_ORGANIZATIONAL` | sprawa, w której kod jest niepożądany                               |
| `NOTES_EXCLUDED`      | uwagi `search`: trzy przyczyny i linia, która wyklucza 90003        |
| `NOTES_LISTED`        | uwagi `search`: załącznik tylko na liście spraw, bez wykluczenia    |
| `NOTES_PARAPHRASED`   | uwagi modelu: wykluczenie „wariantu dużego załącznika” bez numeru   |
| `NOTES_NEGATED`       | uwagi, w których 90003 stoi przy wykluczeniu z zaprzeczeniem        |
| `NOTES_SHORT`         | uwagi `search` w jednej linii, bez żadnego faktu — do raportu       |
| `PROPOSAL`            | propozycja: ponowne zalogowanie w treści dla klienta, nie w uwagach |
| `code_turn()`         | tura modelu z wywołaniami narzędzi o podanych nazwach               |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test helpera importuje je z tego modułu, żeby test
  na żywym modelu nie wziął przez pomyłkę danych testu jednostkowego.
- Dane są zmyślone i nie mają nic wspólnego z zestawem `reading.json`: zestaw zmienia się
  z pomiarami, a próbki tylko razem z oceną.
"""

from collections.abc import Sequence

from app.agent_graphs.search.models import SearchNotes
from app.core_model.graphs.proposal import Proposal
from app.engine_llm import ChatMessage, ToolCall
from tests._helpers.scenarios.reading.models.reading_case import ReadingCase

# Trzy karty, które sprawa każe przeczytać.
CARDS = ("tickets:90001", "tickets:90002", "tickets:90003")

# Trzy przyczyny z kart; ostatnia ma dwa warianty brzmienia.
CAUSES = (("kolejk",), ("blokad",), ("załącznik", "limit operatora"))

# Sprawa z trzema kartami do przeczytania i trzema przyczynami do nazwania.
CASE_CAUSES = ReadingCase(
    case_id              = "c01",
    graphs               = ("search",),
    phenomenon           = "trzy przyczyny",
    text                 = "ZGŁOSZENIE 90961 z 2026-10-15",
    must_read            = CARDS,
    should_read          = (),
    should_not_read      = (),
    should_name          = CAUSES,
    should_exclude       = (),
    should_not_call_code = False,
)

# Ta sama sprawa, a załącznik ma stać w uwagach jako wykluczony.
CASE_EXCLUDED = ReadingCase(
    case_id              = "c02",
    graphs               = ("search",),
    phenomenon           = "wątek wyklucza załącznik",
    text                 = "ZGŁOSZENIE 90962 z 2026-10-15",
    must_read            = CARDS,
    should_read          = (),
    should_not_read      = (),
    should_name          = CAUSES,
    should_exclude       = (("90003", "limit operatora", "dużego załącznika", "duży załącznik"),),
    should_not_call_code = False,
)

# Sprawa z sekcją instrukcji oczekiwaną i dystraktorem.
CASE_DOCS = ReadingCase(
    case_id              = "c03",
    graphs               = ("search",),
    phenomenon           = "kancelaria",
    text                 = "ZGŁOSZENIE 90963 z 2026-10-15",
    must_read            = (),
    should_read          = ("docs:adm-kancelaria-edoreczenia",),
    should_not_read      = ("docs:adm-kancelaria-epuap",),
    should_name          = (("zalog", "przelog"),),
    should_exclude       = (),
    should_not_call_code = False,
)

# Sprawa organizacyjna: kod niepożądany, nic do przeczytania ani nazwania.
CASE_ORGANIZATIONAL = ReadingCase(
    case_id              = "c04",
    graphs               = ("search",),
    phenomenon           = "szkolenie",
    text                 = "ZGŁOSZENIE 90964 z 2026-10-15",
    must_read            = (),
    should_read          = (),
    should_not_read      = (),
    should_name          = (),
    should_exclude       = (),
    should_not_call_code = True,
)

# Uwagi z trzema przyczynami i linią, która wyklucza 90003: przysłówek przed słowem wykluczenia
# kończy się na „nie”, a załącznik stoi bez polskich znaków, jak bywa.
NOTES_EXCLUDED = SearchNotes(internal_notes="\n".join([
    "## Zgłoszenia historyczne",
    "- 90001: zacięta kolejka pobierania",
    "- 90002: plik blokady po aktualizacji",
    "- 90003: zalacznik ponad limit operatora",
    "",
    "Odpowiedź klienta jednoznacznie WYKLUCZA 90003; zostają kolejka i blokada.",
]))

# Uwagi, w których załącznik stoi na liście spraw, a słowo wykluczenia — w innej linii.
NOTES_LISTED = SearchNotes(internal_notes="\n".join([
    "## Zgłoszenia historyczne",
    "- 90003: załącznik ponad limit operatora",
    "",
    "Odpowiedź klienta niczego nie wyklucza.",
]))

# Zdanie modelu z przebiegu na żywym modelu: wyklucza załącznik bez numeru sprawy i bez „limitu
# operatora”, a w tej samej linii stoi zaprzeczenie przy innych przyczynach.
NOTES_PARAPHRASED = SearchNotes(internal_notes=(
    "Odpowiedź klienta wyklucza wariant dużego załącznika, natomiast jednoczesny brak we "
    "wszystkich trzech skrzynkach nie wyklucza zaciętej kolejki ani pliku blokady."
))

# Uwagi, w których 90003 stoi tylko przy słowie wykluczenia z zaprzeczeniem, osobno i razem.
NOTES_NEGATED = SearchNotes(internal_notes="\n".join([
    "Odpowiedź klienta nie wyklucza 90003.",
    "Limit operatora z 90003 pozostaje niewykluczony.",
]))

# Uwagi w jednej linii i bez faktów: raport wypisuje je w jednym wierszu.
NOTES_SHORT = SearchNotes(internal_notes="Przeczytane dwie sprawy.")

# Propozycja: ponowne zalogowanie stoi w treści dla klienta, uwagi go nie wymieniają.
PROPOSAL = Proposal(
    text           = "Prosimy, aby pracownica wylogowała się i zalogowała ponownie.",
    internal_notes = "Sekcja instrukcji o kancelarii e-Doręczeń.",
)


def code_turn(
    names: Sequence[str],  # np. ("find_code_text", "read_docs")
) -> ChatMessage:
    """
    Description:
    Tura modelu z wywołaniami narzędzi o podanych nazwach, bez argumentów i bez wyników — licznik
    narzędzi kodu patrzy wyłącznie na nazwy wywołań.

    Example args:
        names=("find_code_text", "read_docs")

    Example result:
        ChatMessage(role="assistant", tool_calls=[ToolCall(call_id="c1", name="find_code_text"),
                                                  ToolCall(call_id="c2", name="read_docs")])
    """
    calls = [ToolCall(call_id=f"c{number}", name=name) for number, name in enumerate(names, 1)]

    return ChatMessage(role="assistant", tool_calls=calls)
