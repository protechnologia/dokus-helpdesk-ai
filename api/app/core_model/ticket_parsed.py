"""
Description:
Kontrakt sparsowanego zgłoszenia. Jeden `ParsedTicket` to jeden plik JSON w `data/parsed/`, a ten
model rozstrzyga, czy plik jest poprawnym artefaktem. Do indeksu nie trafiają surowe zgłoszenia,
tylko ta struktura: z dwóch pól powstaje wektor, wszystkie jadą w payloadzie Qdranta.

| pole                            | kto wypełnia                    | w wektorze |
|---------------------------------|---------------------------------|------------|
| `ticket_id`, `date`             | graf `parse_ticket`, ze źródła  | nie        |
| `component`                     | model, z treści wątku           | nie        |
| `problem`, `symptoms`           | model                           | tak        |
| `error_codes`, `cause`          | model                           | nie        |
| `solution`                      | model, razem z zastrzeżeniami   | nie        |
| `resolution`                    | model, wartością ze słownika    | nie        |
| `resolution_vocabulary_version` | graf `parse_ticket`             | nie        |
| `questions_summary`             | model                           | nie        |

Przykład — artefakt `data/parsed/33644.json`:

    {
      "ticket_id":         "33644",
      "date":              "2026-03-14",
      "component":         "ePUAP",
      "problem":           "Wysyłka przez ePUAP kończy się błędem komunikacji",
      "symptoms":          "Po kliknięciu Wyślij pojawia się komunikat o braku sieci",
      "error_codes":       ["ERR-4210"],
      "cause":             "Certyfikat bez uprawnienia AddDocumentToSign",
      "solution":          "Wygenerowano certyfikat z właściwym uprawnieniem.",
      "resolution":        "naprawione",
      "questions_summary": "brak",
      "resolution_vocabulary_version": 1
    }

O czym pamiętać przy zmianach:

- Zmiana pól to zmiana kontraktu artefaktu: istniejące pliki przestają się walidować, a nowe pole
  wymaga ponownego przebiegu LLM po korpusie (zasada 7).
- Klucz spoza schematu jest błędem (`extra="forbid"`), a nie cichą stratą.
- Puste pole tekstowe jest odrzucane. Brak wartości zapisuje się jawnie: `brak` albo
  `nie dotyczy`.
- `resolution` sprawdzamy wobec wersji słownika zapisanej w rekordzie, nie wobec dziś
  skonfigurowanej.
"""

from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core_service.builder_embedding_text import build_embedding_text
from app.core_service.loader_dict_resolution import get_resolution_classes

# Jawne wyjścia: pole może powiedzieć „nic tu nie ma", zamiast wymuszać na modelu zmyślenie.
NO_VALUE       = "brak"
NOT_APPLICABLE = "nie dotyczy"


class ParsedTicket(BaseModel):
    """
    Description:
    Sparsowane zgłoszenie — trwały artefakt projektu. Jedna instancja to jeden plik JSON
    w `data/parsed/`.

    Do czego:
    Przebieg LLM jest drogi i jednorazowy, więc artefakt jest trwały, a embeddingi i kolekcje
    Qdranta wymienne: re-index nigdy nie woła modelu ponownie (zasada 7).

    Flow:
        1. Model wypełnia pola z treści całego wątku — także `cause`, której nie ma w żadnej
           kolumnie źródła.
        2. Graf `parse_ticket` dokłada `ticket_id`, `date` i wersję słownika: pochodzą ze źródła
           i konfiguracji, nigdy od modelu.
        3. Indeksacja embeduje `problem` + `symptoms` (`embedding_text()`); wszystkie pola jadą
           w payloadzie.

    Jedna instancja produktu obsługuje jeden helpdeskowany produkt, dlatego nie ma pola `system`:
    nazwa aplikacji to konfiguracja instancji, nie dane rekordu.
    """

    # Model potrafi dołożyć własne pole, często cenne; domyślnie Pydantic skasowałby je bez śladu.
    model_config = ConfigDict(extra="forbid")

    # --- tożsamość: ze źródła, nigdy od modelu ---
    ticket_id: str  = Field(examples=["33644"])
    date:      Date = Field(examples=["2026-03-14"])

    # --- czego dotyczy ---
    # Pole swobodne, nie słownik: warianty zapisu tej samej usługi są pewne, więc bez normalizacji
    # nie nadaje się na filtr Qdranta.
    component: str = Field(examples=["główna aplikacja", "ePUAP", "e-Doręczenia"])

    # --- strona wektora: jedyne dwa pola, z których powstaje embedding ---
    problem:  str = Field(examples=["Wysyłka przez ePUAP kończy się błędem komunikacji"])
    symptoms: str = Field(examples=["Po kliknięciu Wyślij pojawia się komunikat o braku sieci"])

    # --- strona payloadu: z tego powstaje odpowiedź ---
    error_codes: list[str] = Field(default_factory=list, examples=[["ERR-4210", "SQLSTATE 23000"]])
    cause:       str       = Field(examples=["Certyfikat bez uprawnienia AddDocumentToSign"])
    # Zastrzeżenia są częścią tego tekstu, nie osobnym polem; zgubione odwracają sens odpowiedzi.
    solution:    str       = Field(examples=["Wygenerowano certyfikat z właściwym uprawnieniem."])

    # --- klasyfikacja i diagnostyka ---
    resolution: str = Field(examples=["naprawione"])
    # Wersja słownika, z której pochodzi `resolution`: słownik to dane klienta i może się zmienić.
    resolution_vocabulary_version: int = Field(examples=[1])
    # Czego konsultant nie wiedział i o co dopytywał; `brak`, gdy nikt nie dopytywał.
    questions_summary: str = Field(default=NO_VALUE, examples=["pytano o wersję przeglądarki"])

    @field_validator("component", "problem", "symptoms", "cause", "solution", "questions_summary")
    @classmethod
    def _reject_blank(cls, value: str) -> str:          # np. "  "
        """
        Description:
        Odrzuca tekst pusty albo z samych białych znaków. `brak` to odpowiedź, a pusty napis to
        pole pominięte przez model, które w korpusie wyglądałoby jak wypełnione.

        Example args:
            value="   "

        Example result:
            ValueError — trzeba wpisać `brak`

        Raises:
            ValueError: wartość jest pusta albo składa się z białych znaków
        """
        if not value.strip():
            raise ValueError(f"pole nie może być puste — użyj {NO_VALUE!r} albo {NOT_APPLICABLE!r}")

        return value.strip()

    @model_validator(mode="after")
    def _check_resolution_against_vocabulary(self) -> "ParsedTicket":
        """
        Description:
        Sprawdza, czy `resolution` jest wartością ze słownika w wersji zapisanej W REKORDZIE.
        Gdyby sprawdzać wobec wersji skonfigurowanej dziś, edycja słownika unieważniałaby wstecznie
        poprawne artefakty.

        Example args:
            (self, już wypełniony)

        Example result:
            Ta sama instancja, bez zmian

        Raises:
            ValueError: `resolution` jest spoza słownika albo rekord powstał z wersji słownika,
                której ta instalacja nie ma
        """
        vocabulary = get_resolution_classes()

        # Rekordu z innej wersji słownika nie da się ocenić naszą — mówimy to wprost, zamiast
        # zgłaszać mylące „nieznana wartość".
        if self.resolution_vocabulary_version != vocabulary.version:
            raise ValueError(
                f"rekord powstał ze słownika w wersji {self.resolution_vocabulary_version}, "
                f"a ta instalacja ma wersję {vocabulary.version} — re-parsing albo starszy słownik"
            )

        allowed = vocabulary.names()

        if self.resolution not in allowed:
            raise ValueError(
                f"resolution={self.resolution!r} spoza słownika; dozwolone: {', '.join(allowed)}"
            )

        return self

    def embedding_text(self) -> str:
        """
        Description:
        Tekst, z którego powstaje wektor tego rekordu. Składa go `build_embedding_text()` — ta sama
        funkcja, której używa zapytanie w `find_tickets_vector`, więc obie strony porównania nie
        mogą się po cichu rozjechać.

        Example args:
            (brak)

        Example result:
            "Wysyłka przez ePUAP kończy się błędem komunikacji\\nPo kliknięciu Wyślij…"
        """
        text = build_embedding_text(
            problem  = self.problem,
            symptoms = self.symptoms,
        )

        return text
