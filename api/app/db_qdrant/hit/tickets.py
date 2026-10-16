"""
Description:
Trafienie zgłoszenia: to, co oddaje wyszukiwanie w kolekcji zgłoszeń — identyfikator punktu,
podobieństwo i karta zgłoszenia z payloadu.

Wpis odpowiedzi Qdranta:

    {
      "id":      "df3b51f3-9eac-56f3-9f28-6253f23dd731",
      "score":   0.87,
      "payload": {"ticket_id": "33644", "date": "2026-03-14", "problem": "…", "solution": "…", …}
    }

O czym pamiętać przy zmianach:

- Payload zapisuje `TicketPoint` (`point/tickets.py`); tutaj wraca w całości, bez rozbijania
  na pola. Wyjątkiem jest nazwa modelu embeddera: idzie do pola `embedding_model`, a sprawdza ją
  kolekcja.
- Trafienie nie ma wektorów. Punkt z wektorami oddaje odczyt po numerze zgłoszenia.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.db_qdrant.point.base import embedding_model_of, payload_without_model


class TicketHit(BaseModel):
    """
    Description:
    Jedno zgłoszenie tak, jak oddało je wyszukiwanie: podobieństwo i karta z payloadu.

    Do czego:
    Model TRANSPORTU, strona wyszukiwania obok `TicketPoint`. Na nim, a nie na JSON-ie Qdranta,
    pracuje wszystko dalej — próg i narzędzie agenta — więc żaden wołający nie poznaje kształtu
    odpowiedzi usługi.

    Flow:
        1. `from_qdrant()` czyta jeden wpis odpowiedzi wyszukiwania.
        2. Kolekcja oddaje ich listę, od najbardziej podobnego.
        3. Narzędzie przycina progiem i zamienia payload z powrotem na `ParsedTicket`.

    Payload zostaje w całości, bez rozbijania na pola: zapisuje go `TicketPoint`, a drugie miejsce
    wyliczające te same klucze byłoby drugim miejscem, w którym można któryś zgubić.
    """

    model_config = ConfigDict(extra="forbid")

    point_id:        str   = Field(examples=["df3b51f3-9eac-56f3-9f28-6253f23dd731"])
    score:           float = Field(examples=[0.87])
    # Model embeddera, który policzył wektor punktu — po nim kolekcja odmawia mieszania modeli.
    embedding_model: str   = Field(examples=["OPI-PIB/PolDense-150M"])
    payload:         dict  = Field(examples=[{"ticket_id": "33644", "component": "ePUAP"}])

    @property
    def ticket_id(self) -> str:
        """
        Description:
        Numer zgłoszenia, z którego pochodzi trafienie — z payloadu, jak w `TicketPoint`.

        Example args:
            (brak)

        Example result:
            "33644"
        """
        return self.payload.get("ticket_id", "")

    @classmethod
    def from_qdrant(
        cls,
        entry: dict,  # np. {"id": "df3b…", "score": 0.87, "payload": {"ticket_id": "33644"}}
    ) -> "TicketHit":
        """
        Description:
        Czyta jeden wpis odpowiedzi wyszukiwania. Wartości domyślne zamiast indeksowania:
        nierozpoznany kształt ma nie dać `KeyError` trzy warstwy dalej, a brak podobieństwa
        czyta się jako 0.0, które odrzuci każdy próg. Nazwa modelu idzie z payloadu do osobnego
        pola, więc `payload` to sama karta.

        Example args:
            entry={"id": "df3b51f3-…", "score": 0.87,
                   "payload": {"ticket_id": "33644", "embedding_model": "OPI-PIB/PolDense-150M"}}

        Example result:
            TicketHit(point_id="df3b51f3-…", score=0.87, embedding_model="OPI-PIB/PolDense-150M",
                      payload={"ticket_id": "33644"})

        Raises:
            DbQdrantConfigError: punkt nie ma nazwy modelu — kolekcję zbudowano przed jej zapisem
        """
        hit = cls(
            point_id        = str(entry.get("id", "")),
            score           = float(entry.get("score", 0.0)),
            embedding_model = embedding_model_of(entry),
            payload         = payload_without_model(entry),
        )

        return hit
