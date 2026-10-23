"""
Description:
Punkt zgłoszenia w kolekcji Qdranta: identyfikator, dwa nazwane wektory, model embeddera, który je
policzył, i karta zgłoszenia w payloadzie. W tym kształcie zgłoszenie jest zapisywane i w tym
samym wraca z odczytu po numerze.

Punkt w Qdrancie:

    {
      "id":      "df3b51f3-9eac-56f3-9f28-6253f23dd731",
      "vector":  {"problem": [0.0123, …], "sts": [0.0987, …]},
      "payload": {"ticket_id": "33644", "date": "2026-03-14", "problem": "…", "solution": "…", …,
                  "embedding_model": "OPI-PIB/PolDense-150M"}
    }

O czym pamiętać przy zmianach:

- Payload to karta zgłoszenia (`ParsedTicket`), pole w pole. Pole dopisane do karty trzeba
  dopisać w `from_ticket()`, a kolekcję przebudować.
- `solution` jedzie w payloadzie, nigdy w wektorze: szukamy po podobieństwie problemu, a wektor
  z rozwiązaniem mieszałby oba sygnały.
- Wynik wyszukiwania to osobny model (`hit/tickets.py`): nie ma wektorów, a ma podobieństwo.
"""

from pydantic import BaseModel, ConfigDict, Field

from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.db_qdrant.point.base import (
    EMBEDDING_MODEL_KEY,
    embedding_model_of,
    named_vector,
    payload_without_model,
    point_id_for,
)

# Nazwane wektory każdego punktu. `problem` to strona passage, z którą porównywane jest zapytanie
# w runtime; `sts` to wektor symetryczny do porównań zgłoszenie ↔ zgłoszenie.
#
# `sts` dziś nikt nie czyta — pomiar rozstrzygnął wyszukiwanie na korzyść `query→passage`. Budujemy
# go mimo to: usunięcie i późniejszy powrót kosztowałyby pełny re-index (CLAUDE.md -> „Embeddingi
# i prefiksy PolDense").
VECTOR_PROBLEM = "problem"
VECTOR_STS     = "sts"


class TicketPoint(BaseModel):
    """
    Description:
    Jedno zgłoszenie tak, jak trzyma je Qdrant: identyfikator punktu, dwa nazwane wektory
    i karta zgłoszenia w payloadzie.

    Do czego:
    Model TRANSPORTU — opisuje to, co idzie po drucie do jednej usługi, więc leży przy kliencie,
    a nie w `core_model/` (CLAUDE.md -> „Warstwy kodu"). W tym kształcie zgłoszenie wchodzi do
    kolekcji i z niej wraca przy odczycie po numerze.

    Flow:
        1. `from_ticket()` buduje punkt z karty (`ParsedTicket`) i jej dwóch wektorów.
        2. `to_qdrant()` oddaje kształt, którego oczekuje zapis Qdranta.
        3. `from_qdrant()` czyta punkt oddany przez odczyt po identyfikatorze.
    """

    # Klucz spoza kontraktu to pomyłka, nie rozszerzenie — jak w `ParsedTicket`.
    model_config = ConfigDict(extra="forbid")

    point_id:        str         = Field(examples=["df3b51f3-9eac-56f3-9f28-6253f23dd731"])
    vector_problem:  list[float] = Field(examples=[[0.0123, -0.0456]])
    vector_sts:      list[float] = Field(examples=[[0.0987, -0.0654]])
    # Model embeddera, który policzył oba wektory; w Qdrancie stoi w payloadzie, obok karty.
    embedding_model: str         = Field(examples=["OPI-PIB/PolDense-150M"])
    payload:         dict        = Field(examples=[{"ticket_id": "33644", "component": "ePUAP"}])

    @property
    def ticket_id(self) -> str:
        """
        Description:
        Numer zgłoszenia, z którego powstał punkt. Czytany z payloadu: `point_id` to UUID
        wyliczony z numeru i nie da się go odwrócić.

        Example args:
            (brak)

        Example result:
            "33644"
        """
        return self.payload.get("ticket_id", "")

    @classmethod
    def from_ticket(
        cls,
        ticket:          ParsedTicket,  # np. ParsedTicket(ticket_id="33644", …)
        vector_problem:  list[float],   # np. [0.0123, -0.0456] — z embed_passage()
        vector_sts:      list[float],   # np. [0.0987, -0.0654] — z embed_sts()
        embedding_model: str,           # np. "OPI-PIB/PolDense-150M" — z wyniku embeddera
    ) -> "TicketPoint":
        """
        Description:
        Buduje punkt jednego sparsowanego zgłoszenia. Wektory i nazwa modelu przychodzą gotowe:
        embedding to inna granica procesu, a model transportu wołający drugą usługę związałby
        obie zależności.

        Example args:
            ticket=ParsedTicket(ticket_id="33644", …)
            vector_problem=[0.0123, -0.0456]
            vector_sts=[0.0987, -0.0654]
            embedding_model="OPI-PIB/PolDense-150M"

        Example result:
            TicketPoint(point_id="df3b51f3-…", payload={"ticket_id": "33644", …})
        """
        payload = {
            "ticket_id":         ticket.ticket_id,
            # Tekst ISO, nie obiekt daty: JSON nie ma typu daty, a Qdrant sortuje takie teksty
            # poprawnie.
            "date":              ticket.date.isoformat(),
            "component":         ticket.component,
            "problem":           ticket.problem,
            "symptoms":          ticket.symptoms,
            "error_codes":       ticket.error_codes,
            # Nie jest embedowane, ale jedzie: po `cause` odróżnia się trafienia o tym samym
            # objawie i różnych przyczynach (CLAUDE.md -> „Powtarza się objaw").
            "cause":             ticket.cause,
            "excluded_causes":   ticket.excluded_causes,
            "solution":          ticket.solution,
            "resolution":        ticket.resolution,
            "questions_summary": ticket.questions_summary,
            "useful":            ticket.useful,
            "useful_reason":     ticket.useful_reason,
            # Wersja słownika, którą powstało `resolution` — żeby edycja słownika dała się
            # prześledzić bez czytania artefaktu z dysku (zasada 7).
            "resolution_vocabulary_version": ticket.resolution_vocabulary_version,
        }

        point = cls(
            point_id        = point_id_for(ticket.ticket_id),
            vector_problem  = vector_problem,
            vector_sts      = vector_sts,
            embedding_model = embedding_model,
            payload         = payload,
        )

        return point

    @classmethod
    def from_qdrant(
        cls,
        entry: dict,  # np. {"id": "df3b…", "vector": {"problem": […], "sts": […]}, "payload": {…}}
    ) -> "TicketPoint":
        """
        Description:
        Czyta punkt oddany przez odczyt po identyfikatorze. Wektory wracają znormalizowane przez
        Qdranta: ten sam kierunek, niekoniecznie te same liczby co przy zapisie.

        Nazwa modelu idzie z payloadu do osobnego pola, więc `payload` to sama karta, jak przy
        zapisie.

        Example args:
            entry={"id": "df3b51f3-…", "vector": {"problem": [0.5, 0.5], "sts": [0.5, -0.5]},
                   "payload": {"ticket_id": "33644", "embedding_model": "OPI-PIB/PolDense-150M"}}

        Example result:
            TicketPoint(point_id="df3b51f3-…", vector_problem=[0.5, 0.5], …,
                        embedding_model="OPI-PIB/PolDense-150M", payload={"ticket_id": "33644"})

        Raises:
            DbQdrantConfigError: punkt nie ma któregoś z nazwanych wektorów albo nazwy modelu
        """
        point = cls(
            point_id        = str(entry.get("id", "")),
            vector_problem  = named_vector(entry, VECTOR_PROBLEM),
            vector_sts      = named_vector(entry, VECTOR_STS),
            embedding_model = embedding_model_of(entry),
            payload         = payload_without_model(entry),
        )

        return point

    def to_qdrant(self) -> dict:
        """
        Description:
        Oddaje punkt w kształcie zapisu Qdranta. Trzymane na modelu, żeby kolekcja tylko dzieliła
        na partie i wysyłała.

        Example args:
            (brak)

        Example result:
            {"id": "df3b51f3-…", "vector": {"problem": […], "sts": […]}, "payload": {…}}
        """
        wire = {
            "id": self.point_id,
            # Słownik, a nie goła lista: to czyni te wektory NAZWANYMI. Gołą listę kolekcja
            # z kilkoma wektorami odrzuci — i dobrze, bo nie wiadomo, do której przestrzeni idzie.
            "vector": {
                VECTOR_PROBLEM: self.vector_problem,
                VECTOR_STS:     self.vector_sts,
            },
            "payload": {**self.payload, EMBEDDING_MODEL_KEY: self.embedding_model},
        }

        return wire
