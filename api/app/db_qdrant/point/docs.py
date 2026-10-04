"""
Description:
Punkt sekcji dokumentacji w kolekcji Qdranta: identyfikator, nazwany wektor i opis sekcji
w payloadzie. W tym kształcie sekcja jest zapisywana i w tym samym wraca z odczytu po
identyfikatorze.

Punkt w Qdrancie:

    {
      "id":      "c8810a95-5834-535a-badc-c8f9d1c090c7",
      "vector":  {"section": [0.0123, …]},
      "payload": {"section_id": "adm-kancelaria-edoreczenia", "document": "Instrukcja…",
                  "version": "4.12", "title": "Uprawnienie do kancelarii e-Doręczeń", …}
    }

O czym pamiętać przy zmianach:

- Payload to opis sekcji z metryczki (`DocSection`), pole w pole. Treści sekcji tu nie ma: leży
  w Postgresie i daje ją `read_docs`.
- Jeden punkt to jedna sekcja, a jego identyfikator powstaje z `section_id` — ten sam
  identyfikator wskazują wyszukiwanie wektorowe, tekstowe i odczyt.
- Punkt dostaje gotowy wektor. Co się embeduje — całą treść czy sam nagłówek — i czy sekcja
  dzieli się na fragmenty, rozstrzyga pomiar (CLAUDE.md -> p. 8).
- Wynik wyszukiwania to osobny model (`hit/docs.py`): nie ma wektora, a ma podobieństwo.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.core_model.doc_section import DocSection
from app.db_qdrant.point.base import named_vector, point_id_for

# Jedyny wektor punktu dokumentacji: strona passage, z którą porównywane jest zapytanie.
# Nazwany, choć jest jeden — dołożenie drugiego nie zmieni wtedy kształtu punktu.
VECTOR_SECTION = "section"


class DocPoint(BaseModel):
    """
    Description:
    Jedna sekcja dokumentacji tak, jak trzyma ją Qdrant: identyfikator punktu, nazwany wektor
    i opis sekcji w payloadzie.

    Do czego:
    Model TRANSPORTU, jak `TicketPoint`. W tym kształcie sekcja wchodzi do kolekcji i z niej
    wraca przy odczycie po identyfikatorze.

    Flow:
        1. `from_section()` buduje punkt z opisu sekcji (`DocSection`) i jej wektora.
        2. `to_qdrant()` oddaje kształt, którego oczekuje zapis Qdranta.
        3. `from_qdrant()` czyta punkt oddany przez odczyt po identyfikatorze.
    """

    model_config = ConfigDict(extra="forbid")

    point_id:       str         = Field(examples=["c8810a95-5834-535a-badc-c8f9d1c090c7"])
    vector_section: list[float] = Field(examples=[[0.0123, -0.0456]])
    payload:        dict        = Field(examples=[{"section_id": "adm-kancelaria-edoreczenia"}])

    @property
    def section_id(self) -> str:
        """
        Description:
        Identyfikator sekcji, z której powstał punkt. Czytany z payloadu: `point_id` to UUID
        wyliczony z niego i nie da się go odwrócić.

        Example args:
            (brak)

        Example result:
            "adm-kancelaria-edoreczenia"
        """
        return self.payload.get("section_id", "")

    @classmethod
    def from_section(
        cls,
        section:        DocSection,   # np. DocSection(section_id="adm-kancelaria-edoreczenia", …)
        vector_section: list[float],  # np. [0.0123, -0.0456] — z embed_passage()
    ) -> "DocPoint":
        """
        Description:
        Buduje punkt jednej sekcji. Payload to opis sekcji zapisany jak JSON: data jako tekst
        ISO, ścieżka rozdziału jako lista — z niego `DocSection` odtwarza się bez strat.

        Example args:
            section=DocSection(section_id="adm-kancelaria-edoreczenia", version="4.12", …)
            vector_section=[0.0123, -0.0456]

        Example result:
            DocPoint(point_id="c8810a95-…", payload={"section_id": "adm-kancelaria-edoreczenia", …})
        """
        point = cls(
            point_id       = point_id_for(section.section_id),
            vector_section = vector_section,
            payload        = section.model_dump(mode="json"),
        )

        return point

    @classmethod
    def from_qdrant(
        cls,
        entry: dict,  # np. {"id": "c881…", "vector": {"section": […]}, "payload": {…}}
    ) -> "DocPoint":
        """
        Description:
        Czyta punkt oddany przez odczyt po identyfikatorze. Wektor wraca znormalizowany przez
        Qdranta: ten sam kierunek, niekoniecznie te same liczby co przy zapisie.

        Example args:
            entry={"id": "c8810a95-…", "vector": {"section": [0.5, 0.5]},
                   "payload": {"section_id": "adm-kancelaria-edoreczenia"}}

        Example result:
            DocPoint(point_id="c8810a95-…", vector_section=[0.5, 0.5], …)

        Raises:
            DbQdrantConfigError: punkt nie ma nazwanego wektora sekcji
        """
        point = cls(
            point_id       = str(entry.get("id", "")),
            vector_section = named_vector(entry, VECTOR_SECTION),
            payload        = entry.get("payload") or {},
        )

        return point

    def to_qdrant(self) -> dict:
        """
        Description:
        Oddaje punkt w kształcie zapisu Qdranta.

        Example args:
            (brak)

        Example result:
            {"id": "c8810a95-…", "vector": {"section": […]}, "payload": {…}}
        """
        wire = {
            "id":      self.point_id,
            "vector":  {VECTOR_SECTION: self.vector_section},
            "payload": self.payload,
        }

        return wire
