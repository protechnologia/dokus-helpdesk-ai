"""
Description:
Helpery testów: folder na helper, a w nim `helper.py` z logiką, `models/` z modelami danych
(plik na model, nazwany jak model), `constants.py` ze stałymi, `report.py` z raportem,
`measure.py` z przebiegiem spraw na żywym modelu i `samples.py` z próbkami, gdy helper je ma,
oraz `__init__.py`, który wystawia całość poza próbkami. Testy importują z pakietu helpera
(`from tests._helpers.fake_tools import fake_agent_tools`), nigdy z plików w nim wprost; próbki
z ich modułu (`from tests._helpers.scenarios.gates.samples import BLOCK`).

| helper                 | kiedy go brać                                                           |
|------------------------|-------------------------------------------------------------------------|
| `fake_tools`           | atrapy narzędzi agenta z wariantami, narzędzie z padniętym embedderem   |
| `synthetic_code`       | aplikacja syntetyczna: paczka, źródło, opis, mapa symboli, zapytania    |
| `synthetic_docs`       | dokumentacja syntetyczna: indeks wobec paczki, pomiary obu wyszukiwań   |
| `golden_tickets`       | golden set zgłoszeń: pomiar wyszukiwania po znaczeniu i filtra jakości  |
| `golden_anonymization` | golden set anonimizatora: ocena przecieków i zniszczonej wiedzy         |
| `graphs`               | grafy aplikacji: odczyt po nazwie i składanie na atrapach               |
| `postgres`             | narzędzie na prawdziwej tabeli z podmienionym klientem                  |
| `transport`            | test klienta HTTP z podmienionym transportem                            |
| `live`                 | żywy model: konfiguracja, graf na nim, sprawy testu okablowania, raport |
| `scenarios`            | scenariusze grafów z p. 59, folder na scenariusz                        |

O czym pamiętać przy zmianach:

- Plik testu ma same testy: poza nimi tylko `pytestmark`, fixture'y tego pliku i parametry
  liczone przy imporcie. Logika, stałe i dane idą do helpera, którego dotyczą.
- Scenariusze z p. 59 mają wspólny układ (zestaw, sprawy, ocena, raport), więc stoją razem
  w `scenarios/`, folder na scenariusz; tabelka scenariuszy jest w `scenarios/__init__.py`.
  Na górze zostają atrapy i podmiany zależności, infrastruktura żywego modelu i dane pomiarów
  ewaluacyjnych, z których korzystają też testy spoza scenariuszy.
- Folder ma każdy helper, także bez modeli — dla spójności; `models/` dochodzi, gdy helper
  ma dataclassy z danymi, a `constants.py`, gdy ma stałe. Model `InjectionCase` leży
  w `models/injection_case.py`, a `models/__init__.py` niczego nie eksportuje, tylko wymienia
  pliki w tabelce. Klasa, która zbiera wyniki w trakcie przebiegu i składa z nich wydruk, leży
  w `report.py` razem z funkcjami, z których składa linie. Funkcja wspólna dla raportów kilku
  helperów (`field_lines()`) leży w `helper.py` helpera, który ją wystawia.
- `measure.py` przeprowadza sprawy na żywym modelu, ocenia je i zgłasza do raportów. Leży osobno,
  bo potrzebuje i oceny z `helper.py`, i raportu z `report.py`, a raport bierze funkcje
  z `helper.py`: w jednym pliku z oceną powstałby cykl importów.
- `samples.py` trzyma zmyślone dane, na których stoją asercje testów: wejścia, wyniki i skróty
  wołające ocenę. `__init__.py` ich nie wystawia, żeby test na żywym modelu nie wziął przez
  pomyłkę danych testu jednostkowego.
- Każda stała ma nad sobą komentarz, do czego jest potrzebna, a słownik stoi po jednym kluczu
  w linii, z wartościami wyrównanymi po dwukropku.
- Fixture'y raportów stoją w `tests/conftest.py`, bo pytest szuka ich tylko tam.
"""
