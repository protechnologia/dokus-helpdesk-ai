"""
Description:
Helpery testów: folder na helper, a w nim `helper.py` z logiką, `models/` z modelami danych
(plik na model, nazwany jak model), `constants.py` ze stałymi i `report.py` z raportem, gdy
helper je ma, oraz `__init__.py`, który wystawia całość. Testy importują z pakietu helpera
(`from tests._helpers.fake_tools import fake_agent_tools`), nigdy z plików w nim wprost.

| helper           | kiedy go brać                                                              |
|------------------|----------------------------------------------------------------------------|
| `fake_tools`     | komplet atrap narzędzi agenta i warianty, narzędzie z padniętym embedderem |
| `synthetic_code` | aplikacja syntetyczna: paczka, źródło, opis, mapa symboli i zapytania      |
| `postgres`       | narzędzie na prawdziwej tabeli z podmienionym klientem                     |
| `transport`      | test klienta HTTP z podmienionym transportem                               |
| `live`           | żywy model: konfiguracja, graf na nim i raport zużycia z wydrukiem rozmowy |
| `scenarios`      | scenariusze grafów z p. 59: wstrzyknięcia, bramki, „Popraw”, pytania       |

O czym pamiętać przy zmianach:

- Scenariusze z p. 59 mają wspólny układ (zestaw, sprawy, ocena, raport), więc stoją razem
  w `scenarios/`, folder na scenariusz; tabelka scenariuszy jest w `scenarios/__init__.py`.
  Na górze zostają atrapy i podmiany zależności oraz infrastruktura żywego modelu, z której
  korzystają też testy spoza scenariuszy.

- Folder ma każdy helper, także bez modeli — dla spójności; `models/` dochodzi, gdy helper
  ma dataclassy z danymi, a `constants.py`, gdy ma stałe. Model `InjectionCase` leży
  w `models/injection_case.py`, a `models/__init__.py` niczego nie eksportuje, tylko wymienia
  pliki w tabelce. Klasa, która zbiera wyniki w trakcie przebiegu i składa z nich wydruk, leży
  w `report.py` razem z funkcjami, z których składa linie. Funkcja wspólna dla raportów kilku
  helperów (`field_lines()`) leży w `helper.py` helpera, który ją wystawia.
- Każda stała ma nad sobą komentarz, do czego jest potrzebna, a słownik stoi po jednym kluczu
  w linii, z wartościami wyrównanymi po dwukropku.
- Fixture'y raportów stoją w `tests/conftest.py`, bo pytest szuka ich tylko tam.
"""
