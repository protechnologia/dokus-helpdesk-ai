"""
Description:
Helpery scenariuszy ewaluacyjnych grafów na żywym modelu (p. 59). Każdy ma ten sam układ:
zestaw z `data/safe/golden/` wczytany do sekcji i spraw, ocena jednej sprawy, przebieg spraw na
żywym modelu i raport, który pytest wypisuje po przebiegu. Testy importują z pakietu scenariusza
(`from tests._helpers.scenarios.gates import judge_gate_case`); ten plik niczego nie eksportuje.

| scenariusz   | zestaw            | co sprawdza                                                 |
|--------------|-------------------|-------------------------------------------------------------|
| `injections` | `injections.json` | czy polecenie wstrzyknięte w wejście albo materiał przebija |
| `gates`      | `gates.json`      | werdykt bramki na sprawie łamiącej, poprawnej i pułapce     |
| `polish`     | `polish.json`     | czy „Popraw” zmienia formę notatek, a nie ich treść         |
| `questions`  | `questions.json`  | czy pytania padają tylko przy konkurujących przyczynach     |
| `code`       | `code.json`       | czy graf cytuje jako przyczynę właściwy plik kodu           |

O czym pamiętać przy zmianach:

- Nowy scenariusz to nowy folder obok, w tym samym układzie: `helper.py`, `models/`,
  `constants.py`, `report.py`, `measure.py`, `samples.py` i `__init__.py`, oraz fixture raportu
  w `tests/conftest.py`.
- Raporty wypisują pola wyniku przez `field_lines()` z `injections`, a każdy scenariusz ma
  własną kopię `META_KEY`; wspólny szkielet scenariuszy czeka na komplet grafów z p. 59.
"""
