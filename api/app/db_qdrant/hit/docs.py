"""
Description:
Trafienie w dokumentacji: to, co oddaje wyszukiwanie w kolekcji dokumentacji — identyfikator
punktu, podobieństwo i opis sekcji z payloadu. Trafia się we FRAGMENT sekcji, więc kilka trafień
może wskazywać tę samą sekcję.

Wpis odpowiedzi Qdranta:

    {
      "id":      "bc925b88-f5ba-5cda-aa43-65a036e4820d",
      "score":   0.74,
      "payload": {"section_id": "adm-kancelaria-edoreczenia", "document": "Instrukcja…",
                  "version": "4.12", "title": "Uprawnienie do kancelarii e-Doręczeń", …}
    }

O czym pamiętać przy zmianach:

- Payload zapisuje `DocPoint` (`point/docs.py`) i jest to opis sekcji z metryczki, bez treści
  i bez numeru fragmentu.
- Trafienia tej samej sekcji zwija do jednego wyniku narzędzie `find_docs_vector`
  (CLAUDE.md -> p. 8), nie kolekcja.
"""

from pydantic import BaseModel, ConfigDict, Field


class DocHit(BaseModel):
    """
    Description:
    Jeden fragment sekcji dokumentacji tak, jak oddało go wyszukiwanie: podobieństwo i opis
    sekcji z payloadu.

    Do czego:
    Model TRANSPORTU, strona wyszukiwania obok `DocPoint`. Z niego `find_docs_vector` zbuduje wiersz
    spisu; treści sekcji nie niesie.

    Flow:
        1. `from_qdrant()` czyta jeden wpis odpowiedzi wyszukiwania.
        2. Kolekcja oddaje ich listę, od najbardziej podobnego.
    """

    model_config = ConfigDict(extra="forbid")

    point_id: str   = Field(examples=["bc925b88-f5ba-5cda-aa43-65a036e4820d"])
    score:    float = Field(examples=[0.74])
    payload:  dict  = Field(examples=[{"section_id": "adm-kancelaria-edoreczenia"}])

    @property
    def section_id(self) -> str:
        """
        Description:
        Identyfikator sekcji, z której pochodzi trafienie — z payloadu, jak w `DocPoint`.

        Example args:
            (brak)

        Example result:
            "adm-kancelaria-edoreczenia"
        """
        return self.payload.get("section_id", "")

    @classmethod
    def from_qdrant(
        cls,
        entry: dict,  # np. {"id": "c881…", "score": 0.74, "payload": {"section_id": "adm-…"}}
    ) -> "DocHit":
        """
        Description:
        Czyta jeden wpis odpowiedzi wyszukiwania; brak podobieństwa czyta się jako 0.0, które
        odrzuci każdy próg.

        Example args:
            entry={"id": "bc925b88-…", "score": 0.74,
                   "payload": {"section_id": "adm-kancelaria-edoreczenia"}}

        Example result:
            DocHit(point_id="bc925b88-…", score=0.74, payload={"section_id": "adm-…"})
        """
        hit = cls(
            point_id = str(entry.get("id", "")),
            score    = float(entry.get("score", 0.0)),
            payload  = entry.get("payload") or {},
        )

        return hit
