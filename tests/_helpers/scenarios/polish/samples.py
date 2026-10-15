"""
Description:
Próbki do testów samego helpera „Popraw” (`tests/unit/test_polish_report.py`): sprawa z listami
słów potocznych, faktów i pułapek oraz poprawiony tekst, który żadnej z list nie łamie. Dzięki nim
plik testu to same testy, a dane, na których stoją asercje, leżą obok helpera, którego dotyczą.

| co      | do czego                                                                   |
|---------|----------------------------------------------------------------------------|
| `CASE`  | notatki z dwoma słowami potocznymi, trzema faktami i jedną pułapką         |
| `CLEAN` | redakcja tych notatek bez słów potocznych, z faktami, bez nowych liczb     |

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test helpera importuje je z tego modułu, żeby test
  na żywym modelu nie wziął przez pomyłkę danych testu jednostkowego.
- Dane są zmyślone i nie mają nic wspólnego z zestawem `polish.json`: zestaw zmienia się
  z pomiarami, a próbki tylko razem z oceną.
"""

from tests._helpers.scenarios.polish.models.polish_case import PolishCase

# Notatki pisane w pośpiechu: dwa słowa potoczne, trzy fakty bez odmiany i pułapka — dopisek
# o rozdzielczości, którego w notatkach nie ma.
CASE = PolishCase(
    case_id    = "s04",
    phenomenon = "dodatkowy krok kusi do dopisania",
    text       = "limit do epuap to 5 MB, a pdf ma 12 MB i sie wywala, bedzie cacy",
    colloquial = ("wywala", "cacy"),
    kept       = ("5 MB", "12 MB", "ePUAP"),
    tempting   = ("rozdzielczo",),
)

# Redakcja notatek `CASE` zgodna ze wszystkimi listami; numer kroku na początku linii nie jest
# nową liczbą.
CLEAN = "Dzień dobry,\nlimit ePUAP to 5 MB, a plik PDF ma 12 MB.\n1. Prosimy zmniejszyć plik."
