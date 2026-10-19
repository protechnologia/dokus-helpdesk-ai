"""
Description:
Proste, uniwersalne funkcje bez wiedzy o anonimizacji: da się je opisać i przetestować, ani razu
nie mówiąc o danych osobowych. Importuje się z modułów
(`from anonymizer_app.core_util.fold import fold_word`); ten plik niczego nie eksportuje.

| plik          | co zawiera                                                      |
|---------------|-----------------------------------------------------------------|
| `fold.py`     | `fold_word()`, `fold_text()` — małe litery bez polskich znaków  |
| `chunks.py`   | `split_into_chunks()` — części tekstu do limitu znaków          |
| `spans.py`    | `is_inside()` — czy zakres leży w którymś z podanych            |
| `markdown.py` | `read_document()` — dokument bez komentarzy redakcyjnych        |

Operacje, które wiedzą o znacznikach, osobach i miejscach danych, leżą w `core_service/`.
"""
