"""
Description:
Modele danych klienta, które wchodzą do promptów: słownik rozstrzygnięć i zestawy reguł. Treść
leży w `core_text/dict_*.json`, a czytają ją `core_service/loader_dict_*.py`. Plik nazywa się
jak jego model; importuje się z modułów.

| plik                       | model                  | co opisuje                              |
|----------------------------|------------------------|-----------------------------------------|
| `resolution_class.py`      | `ResolutionClass`      | jeden rodzaj rozstrzygnięcia zgłoszenia |
| `resolution_vocabulary.py` | `ResolutionVocabulary` | słownik rozstrzygnięć i jego wersja     |
| `rule_set.py`              | `RuleSet`              | zestaw reguł klienta dla jednego grafu  |
"""
