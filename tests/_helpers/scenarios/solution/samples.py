"""
Description:
Próbki do testów samego helpera rozwiązania (`tests/unit/test_solution_report.py`): sprawy
z faktami wymaganymi, wzmianką oczekiwaną i niepożądaną oraz wyniki z treścią i bez niej. Dzięki
nim plik testu to same testy, a dane, na których stoją asercje, leżą obok helpera, którego
dotyczą.

| co              | do czego                                                            |
|-----------------|---------------------------------------------------------------------|
| `CASE_WARNING`  | sprawa z dwoma faktami wymaganymi: krok i jego nieodwracalność      |
| `CASE_DONE`     | sprawa z wzmianką niepożądaną: krok, który klient już wykonał       |
| `CASE_STEP`     | sprawa z wzmianką oczekiwaną: ten sam krok przy zgłoszeniu bez wątku |
| `WARNED`        | propozycja z krokiem i jego nieodwracalnością                       |
| `BARE`          | propozycja z samym krokiem, bez nieodwracalności                    |
| `NOTES_ONLY`    | wynik bez treści dla klienta: same uwagi z tymi samymi słowami      |
| `QUESTIONED`    | propozycja z pytaniem do klienta, cytatem i adresem z „?”           |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test helpera importuje je z tego modułu, żeby test
  na żywym modelu nie wziął przez pomyłkę danych testu jednostkowego.
- Dane są zmyślone i nie mają nic wspólnego z zestawem `solution.json`: zestaw zmienia się
  z pomiarami, a próbki tylko razem z oceną.
"""

from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.proposal_notes import ProposalNotes
from tests._helpers.scenarios.solution.models.solution_case import SolutionCase

# Sprawa z dwoma faktami wymaganymi w treści dla klienta: krok nieodwracalny i jego skutek.
CASE_WARNING = SolutionCase(
    case_id            = "r03",
    phenomenon         = "krok nieodwracalny z karty",
    text               = "ZGŁOSZENIE 1",
    card_changes       = {"90002": {"solution": "…"}},
    must_mention       = (
        ("ponowne pobr", "ponownego pobier"),
        ("nieodwracaln", "nie da się usunąć"),
    ),
    should_mention     = (),
    should_not_mention = (),
)

# Sprawa z wzmianką niepożądaną: krok, który wątek pokazuje jako wykonany, nie ma wrócić.
CASE_DONE = SolutionCase(
    case_id            = "r01",
    phenomenon         = "krok już wykonany",
    text               = "ZGŁOSZENIE 2",
    card_changes       = {},
    must_mention       = (),
    should_mention     = (),
    should_not_mention = (("ręczn",), ("operator",)),
)

# Sprawa z wzmianką oczekiwaną: ten sam krok przy zgłoszeniu bez wątku ma się pojawić.
CASE_STEP = SolutionCase(
    case_id            = "r02",
    phenomenon         = "krok z karty",
    text               = "ZGŁOSZENIE 3",
    card_changes       = {},
    must_mention       = (),
    should_mention     = (("ręczn",), ("operator",)),
    should_not_mention = (),
)

# Propozycja z krokiem i jego nieodwracalnością, zapisana z wielkich liter i bez polskich znaków.
WARNED = Proposal(
    text           = "Kroki do wykonania:\n1. Prosimy NIE uruchamiac ponownego pobierania, "
                     "bo takich wpisow nie da sie usunac.",
    internal_notes = "",
)

# Propozycja z samym krokiem: przesyłkę odebrać ręcznie u operatora, bez nieodwracalności.
BARE = Proposal(
    text           = "Kroki do wykonania:\n1. Prosimy odebrać przesyłkę ręcznie u operatora; "
                     "ponowne pobranie uruchomimy po naszej stronie.",
    internal_notes = "",
)

# Wynik bez treści dla klienta: same uwagi, w których stoją słowa wszystkich faktów.
NOTES_ONLY = ProposalNotes(
    internal_notes = "Ponowne pobranie tworzy wpisy, których nie da się usunąć; operator ręcznie.",
)

# Propozycja z jednym pytaniem do klienta; znak zapytania stoi też w cytacie komunikatu z ekranu,
# w adresie i w uwagach, a żaden z nich pytaniem do klienta nie jest.
QUESTIONED = Proposal(
    text           = "Kroki do wykonania:\n"
                     "1. Czy przesyłki przestały przychodzić po aktualizacji?\n"
                     "2. Przy komunikacie „Czy zapisać zmiany?” prosimy wybrać Tak.\n"
                     "3. Instrukcja: https://pomoc.example/szukaj?q=blokada",
    internal_notes = "Czy klient aktualizował aplikację?",
)
