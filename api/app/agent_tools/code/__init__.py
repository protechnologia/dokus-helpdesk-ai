"""
Description:
Narzędzia agenta na kodzie źródłowym aplikacji. Kod czyta się inaczej niż zgłoszenia
i dokumentację: model chodzi po plikach, a przechodzi przez wiele więcej, niż potrzebuje do
odpowiedzi. Dlatego odczyt kodu źródeł nie tworzy — robi to osobne narzędzie cytujące, którym
model wskazuje fragment powodujący opisane zachowanie.

| co             | co zawiera                                                             |
|----------------|------------------------------------------------------------------------|
| `fake_code.py` | zmyślone pliki, na których stoją atrapy narzędzi kodu                  |
| `quote_code/`  | cytowanie fragmentu pliku: przyczyna trafia na listę źródeł odpowiedzi |

Narzędzia właściwe stoją na paczce kodu na dysku (`CodePackage` z
`core_service/loader_code_package.py`), bez bazy. Szukanie, odczyt pliku i symbolu, spis katalogu
i opis projektu dojdą jako kolejne katalogi (CLAUDE.md -> p. 62–66).

Narzędzie importuje się z jego pakietu
(`from app.agent_tools.code.quote_code import QuoteCodeTool`), nie stąd.
"""
