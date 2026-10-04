"""
Description:
Narzędzia agenta na dokumentacji produktu. Idą dwustopniowo: spis treści i oba wyszukiwania
oddają wiersze z identyfikatorem sekcji, a treść daje dopiero odczyt — i tylko on cytuje.

| co                  | co zawiera                                                               |
|---------------------|--------------------------------------------------------------------------|
| `base.py`           | wiersz i nagłówek sekcji w tekście dla modelu, wspólne dla całej czwórki |
| `fake_docs.py`      | zmyślona dokumentacja, na której stoją atrapy całej czwórki              |
| `list_docs/`        | spis treści                                                              |
| `find_docs_vector/` | wyszukiwanie po znaczeniu (embedder i Qdrant)                            |
| `find_docs_text/`   | wyszukiwanie po dosłownym brzmieniu i po słowach (Postgres)              |
| `read_docs/`        | treść sekcji po identyfikatorach                                         |

Narzędzie importuje się z jego pakietu
(`from app.agent_tools.docs.read_docs import FakeReadDocsTool`), nie stąd. Cały folder jest
opcjonalny: instancja bez dokumentacji nie rejestruje żadnego z tych narzędzi.
"""
