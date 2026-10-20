from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

# Nazwy materiałów, indeksów i stanów czyta front, więc są po angielsku, jak `verdict`. Materiał
# nazywa się jak `SourceRef.source`.
Material   = Literal["tickets", "docs", "code"]
IndexName  = Literal["cards", "threads", "sections", "fragments", "package"]
IndexState = Literal["missing", "empty", "built"]


class IndexStatus(BaseModel):
    """
    Description:
    Stan jednego indeksu materiału: którego materiału i którego indeksu dotyczy oraz ile niesie
    elementów — `None`, gdy indeksu nie ma.

    Do czego:
    Trasa `GET /instance` pokazuje, na czym stoją dziś narzędzia agenta. Brak indeksu i pusty
    indeks to różne sytuacje: pierwszy kończy wywołanie narzędzia błędem konfiguracji, drugi
    daje pusty wynik, który wygląda jak „materiał nic o tym nie mówi". Stan (`state`) wynika
    z liczby, więc nie da się go z nią rozjechać.

    | materiał  | indeks      | co liczy `count`                         | narzędzia na nim       |
    |-----------|-------------|------------------------------------------|------------------------|
    | `tickets` | `cards`     | punkty kolekcji zgłoszeń w Qdrancie      | `find_tickets_vector`, |
    |           |             |                                          | `read_tickets_card`    |
    | `tickets` | `threads`   | wiersze tabeli zgłoszeń w Postgresie     | `find_tickets_text`,   |
    |           |             |                                          | `read_tickets_thread`  |
    | `docs`    | `sections`  | wiersze tabeli dokumentacji w Postgresie | `list_docs`,           |
    |           |             |                                          | `find_docs_text`,      |
    |           |             |                                          | `read_docs`            |
    | `docs`    | `fragments` | punkty kolekcji dokumentacji w Qdrancie  | `find_docs_vector`     |
    | `code`    | `package`   | pliki paczki kodu według metryczki       | sześć narzędzi kodu    |
    """

    model_config = ConfigDict(extra="forbid")

    material: Material   = Field(examples=["tickets"])
    index:    IndexName  = Field(examples=["cards"])
    count:    int | None = Field(ge=0, examples=[171])

    @computed_field
    @property
    def state(self) -> IndexState:
        """
        Description:
        Stan indeksu z liczby elementów: bez liczby indeksu nie ma, zero to indeks pusty.

        Example args:
            (brak)

        Example result:
            "built"
        """
        # --- indeksu nie ma: narzędzia na nim kończą się błędem konfiguracji ---
        if self.count is None:
            return "missing"

        # --- indeks jest, ale pusty: narzędzia na nim oddają puste wyniki ---
        if self.count == 0:
            return "empty"

        return "built"
