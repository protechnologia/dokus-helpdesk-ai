"""
Description:
Modele danych klienta: słownik rozstrzygnięć i zestawy reguł, które wchodzą do promptów, oraz
słownik maili, którym normalizer czyści wątki kanału „Automat mailowy”. Słownik rozstrzygnięć
i reguły leżą w `core_text/dict_*.json`, a czytają je `core_service/loader_dict_*.py`; słownik
maili leży w `data/unsafe/mail/` (zmyślony, do testów, w `data/safe/mail/`), a czyta go
`core_service/loader_mail_dictionary.py`. Plik nazywa się jak jego model; importuje się
z modułów.

| plik                       | model                  | co opisuje                                 |
|----------------------------|------------------------|--------------------------------------------|
| `mail_templates.py`        | `MailTemplates`        | skróty szablonów maili (`slownik.json`)    |
| `resolution_class.py`      | `ResolutionClass`      | jeden rodzaj rozstrzygnięcia zgłoszenia    |
| `resolution_vocabulary.py` | `ResolutionVocabulary` | słownik rozstrzygnięć i jego wersja        |
| `rule_set.py`              | `RuleSet`              | zestaw reguł klienta dla jednego grafu     |
| `vendor_names.py`          | `VendorNames`          | nazwy dostawcy z podpisów (`nazwy.json`)   |
"""
