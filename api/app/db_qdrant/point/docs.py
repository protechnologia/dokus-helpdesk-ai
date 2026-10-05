"""
Description:
Punkt dokumentacji w kolekcji Qdranta: jeden FRAGMENT sekcji — identyfikator, nazwany wektor
fragmentu i opis całej sekcji w payloadzie. Sekcja ma tyle punktów, na ile fragmentów pocięto
jej treść; krótka ma jeden.

Punkt w Qdrancie:

    {
      "id":      "bc925b88-f5ba-5cda-aa43-65a036e4820d",
      "vector":  {"section": [0.0123, …]},
      "payload": {"section_id": "adm-kancelaria-edoreczenia", "document": "Instrukcja…",
                  "version": "4.12", "title": "Uprawnienie do kancelarii e-Doręczeń", …}
    }

O czym pamiętać przy zmianach:

- Payload to opis sekcji z metryczki (`DocSection`), pole w pole, ten sam w każdym fragmencie
  sekcji. Treści tu nie ma — ani sekcji, ani fragmentu: leży w Postgresie i daje ją `read_docs`.
- Identyfikator punktu powstaje z `section_id` i numeru fragmentu, więc ponowna indeksacja trafia
  w te same punkty. Jednostką wyniku zostaje sekcja: wyszukiwanie wektorowe, tekstowe i odczyt
  wskazują ten sam `section_id`, który punkt niesie w payloadzie.
- Punkt dostaje gotowy wektor. Tekst fragmentu składa `core_service/builder_doc_embedding_text.py`.
- Punkt się zapisuje, ale nie czyta z powrotem: z kolekcji wraca trafienie (`hit/docs.py`),
  które nie ma wektora, a ma podobieństwo.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.core_model.docs.doc_section import DocSection
from app.db_qdrant.point.base import point_id_for

# Jedyny wektor punktu dokumentacji: strona passage, z którą porównywane jest zapytanie.
# Nazwany, choć jest jeden — dołożenie drugiego nie zmieni wtedy kształtu punktu.
VECTOR_SECTION = "section"


class DocPoint(BaseModel):
    """
    Description:
    Jeden fragment sekcji dokumentacji tak, jak trzyma go Qdrant: identyfikator punktu, nazwany
    wektor i opis sekcji w payloadzie.

    Do czego:
    Model TRANSPORTU, jak `TicketPoint`. W tym kształcie fragment wchodzi do kolekcji przy
    imporcie dokumentacji.

    Flow:
        1. `from_fragment()` buduje punkt z opisu sekcji (`DocSection`), numeru fragmentu
           i jego wektora.
        2. `to_qdrant()` oddaje kształt, którego oczekuje zapis Qdranta.
    """

    model_config = ConfigDict(extra="forbid")

    point_id:       str         = Field(examples=["bc925b88-f5ba-5cda-aa43-65a036e4820d"])
    vector_section: list[float] = Field(examples=[[0.0123, -0.0456]])
    payload:        dict        = Field(examples=[{"section_id": "adm-kancelaria-edoreczenia"}])

    @property
    def section_id(self) -> str:
        """
        Description:
        Identyfikator sekcji, z której pochodzi fragment. Czytany z payloadu: `point_id` to UUID
        wyliczony z niego i nie da się go odwrócić.

        Example args:
            (brak)

        Example result:
            "adm-kancelaria-edoreczenia"
        """
        return self.payload.get("section_id", "")

    @classmethod
    def from_fragment(
        cls,
        section:        DocSection,   # np. DocSection(section_id="adm-kancelaria-edoreczenia", …)
        fragment:       int,          # numer fragmentu w sekcji, od zera
        vector_section: list[float],  # np. [0.0123, -0.0456] — z embed_passage()
    ) -> "DocPoint":
        """
        Description:
        Buduje punkt jednego fragmentu sekcji. Payload to opis sekcji zapisany jak JSON: data
        jako tekst ISO, ścieżka rozdziału jako lista — z niego `DocSection` odtwarza się bez
        strat.

        Example args:
            section=DocSection(section_id="adm-kancelaria-edoreczenia", version="4.12", …)
            fragment=0
            vector_section=[0.0123, -0.0456]

        Example result:
            DocPoint(point_id="bc925b88-…", payload={"section_id": "adm-kancelaria-edoreczenia", …})
        """
        point = cls(
            # `#` nie występuje w identyfikatorze sekcji, więc dwie sekcje nie dadzą tego samego
            # punktu.
            point_id       = point_id_for(f"{section.section_id}#{fragment}"),
            vector_section = vector_section,
            payload        = section.model_dump(mode="json"),
        )

        return point

    def to_qdrant(self) -> dict:
        """
        Description:
        Oddaje punkt w kształcie zapisu Qdranta.

        Example args:
            (brak)

        Example result:
            {"id": "bc925b88-…", "vector": {"section": […]}, "payload": {…}}
        """
        wire = {
            "id":      self.point_id,
            "vector":  {VECTOR_SECTION: self.vector_section},
            "payload": self.payload,
        }

        return wire
