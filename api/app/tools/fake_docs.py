"""
Description:
Zmyślona dokumentacja, na której stoją atrapy wszystkich narzędzi dokumentacji (`list_docs`,
`find_docs_vector`, `find_docs_text`, `read_docs`). Jedno miejsce, żeby identyfikator zwrócony
przez atrapę wyszukiwania dało się odczytać atrapą odczytu — tak jak na produkcji.

| sekcja                       | dokument                  | po co jest w zestawie  |
|------------------------------|---------------------------|------------------------|
| `adm-kancelaria-edoreczenia` | Instrukcja administratora | cel wyszukiwania       |
| `adm-kancelaria-epuap`       | Instrukcja administratora | dystraktor: inny kanał |
| `usr-wysylka-status-w-toku`  | Instrukcja użytkownika    | krok nieodwracalny     |
| `usr-komunikat-brak-serwera` | Instrukcja użytkownika    | dosłowny komunikat     |

O czym pamiętać przy zmianach:

- Treść jest wymyślona, nigdy kopiowana z prawdziwej instrukcji ani z korpusu.
- Identyfikatory są stałe: testy grafów odwołują się do nich wprost.
"""

from datetime import date

from app.model.doc_section import DocSection

ADMIN_GUIDE = {"document": "Instrukcja administratora", "version": "4.12", "date": date(2026, 5, 4)}
USER_GUIDE  = {"document": "Instrukcja użytkownika",    "version": "4.12", "date": date(2026, 5, 4)}


def default_sections() -> list[DocSection]:
    """
    Description:
    Cztery zmyślone sekcje z dwóch dokumentów — w kolejności, w jakiej stoją w listingu.

    Example args:
        (brak)

    Example result:
        [DocSection(section_id="adm-kancelaria-edoreczenia", …), DocSection(…), …]
    """
    sections = [
        DocSection(
            **ADMIN_GUIDE,
            section_id   = "adm-kancelaria-edoreczenia",
            chapter_path = ["Uprawnienia", "Kancelaria"],
            title        = "Uprawnienie do kancelarii e-Doręczeń",
            description  = "Kto i gdzie nadaje uprawnienie do kancelarii e-Doręczeń i kiedy działa",
        ),
        DocSection(
            **ADMIN_GUIDE,
            section_id   = "adm-kancelaria-epuap",
            chapter_path = ["Uprawnienia", "Kancelaria"],
            title        = "Uprawnienie do skrzynki ePUAP",
            description  = "Kto nadaje uprawnienie do skrzynki ePUAP i jak je odebrać",
        ),
        DocSection(
            **USER_GUIDE,
            section_id   = "usr-wysylka-status-w-toku",
            chapter_path = ["Wysyłka", "ePUAP"],
            title        = "Status „W toku” przy wysyłce ePUAP",
            description  = "Co znaczy status „W toku” i dlaczego nie wolno ponawiać wysyłki",
        ),
        DocSection(
            **USER_GUIDE,
            section_id   = "usr-komunikat-brak-serwera",
            chapter_path = ["Komunikaty błędów"],
            title        = "Komunikat „Nie udało się skomunikować z serwerem”",
            description  = "Możliwe przyczyny komunikatu zależnie od czynności",
        ),
    ]

    return sections


def default_texts() -> dict[str, str]:
    """
    Description:
    Treść każdej sekcji z `default_sections()`, po identyfikatorze — to, co oddaje odczyt.

    Example args:
        (brak)

    Example result:
        {"adm-kancelaria-edoreczenia": "Uprawnienie do kancelarii e-Doręczeń nadaje…", …}
    """
    texts = {
        "adm-kancelaria-edoreczenia": (
            "Uprawnienie do kancelarii e-Doręczeń nadaje administrator w Ustawienia → Uprawnienia "
            "→ Kancelaria; działa po ponownym zalogowaniu użytkownika."
        ),
        "adm-kancelaria-epuap": (
            "Uprawnienie do skrzynki ePUAP nadaje administrator w Ustawienia → Uprawnienia → "
            "Kancelaria, zakładka ePUAP. Odebranie uprawnienia działa od razu."
        ),
        "usr-wysylka-status-w-toku": (
            "Status „W toku” przy wysyłce ePUAP oznacza nadawanie w trakcie — ponowna wysyłka "
            "utworzy drugie, nieodwracalne doręczenie."
        ),
        "usr-komunikat-brak-serwera": (
            "Komunikat „Nie udało się skomunikować z serwerem” przy podpisie wskazuje na limity "
            "zasobów serwera, a w pierwszych dniach roku — na brak sekwencji numeracji."
        ),
    }

    return texts
