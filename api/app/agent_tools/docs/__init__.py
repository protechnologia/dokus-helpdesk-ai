"""
Description:
Narzędzia agenta na dokumentacji produktu. Idą dwustopniowo: spis treści i oba wyszukiwania
oddają opisy sekcji z identyfikatorem, a treść daje dopiero odczyt — i tylko on cytuje.

| co                  | co zawiera                                                  |
|---------------------|-------------------------------------------------------------|
| `fake_docs.py`      | zmyślona dokumentacja, na której stoją atrapy całej czwórki |
| `list_docs/`        | spis treści                                                 |
| `find_docs_vector/` | wyszukiwanie po znaczeniu (embedder i Qdrant)               |
| `find_docs_text/`   | wyszukiwanie po dosłownym brzmieniu i po słowach (Postgres) |
| `read_docs/`        | treść sekcji po identyfikatorach                            |

Opis sekcji (`DocSection`) jest w wyniku każdego z nich ten sam, więc identyfikator do odczytu
stoi zawsze w tym samym polu.

Narzędzie importuje się z jego pakietu
(`from app.agent_tools.docs.read_docs import FakeReadDocsTool`), nie stąd. Cały folder jest
opcjonalny: instancja bez dokumentacji nie rejestruje żadnego z tych narzędzi.
"""
