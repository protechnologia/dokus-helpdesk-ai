"""
Description:
Operacje anonimizacji wspólne dla węzłów grafu: znaczniki, odmiany osób, morfologia i zamiana
miejsc danych. Nazwa pliku mówi, co robi i czego dotyczy (`<rola>_<przedmiot>`, jak w `api`).
Importuje się z modułów
(`from anonymizer_app.core_service.replacer_found import replace_found`); ten plik niczego nie
eksportuje.

| plik                     | co zawiera                                                         |
|--------------------------|--------------------------------------------------------------------|
| `finder_markers.py`      | `marker_spans()` — zakresy znaczników `{RODZAJ}` w tekście         |
| `finder_word_forms.py`   | `find_word_forms()` — odmiany wskazanego imienia albo nazwiska     |
| `analyzer_morphology.py` | `analyse_word()` — lematy słowa ze słownika Morfeusz2 (SGJP)       |
| `replacer_found.py`      | `choose_found()`, `replace_found()` — wybór i zamiana miejsc danych |
"""
