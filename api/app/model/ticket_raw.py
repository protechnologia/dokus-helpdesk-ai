from datetime import date as Date

from pydantic import BaseModel, Field

from app.model.ticket_raw_comment import RawComment

# Początek linii z tematem w tekście wątku — tak ją zapisuje `as_thread()` i po tym znajduje
# `subject_of_thread()`.
SUBJECT_PREFIX = "Temat: "


class RawTicket(BaseModel):
    """
    Description:
    Jedno zgłoszenie źródłowe w znormalizowanym kształcie. Tylko ten kształt widzi reszta systemu
    — nazwy kolumn, HTML i układ pliku zostają w czytniku (CLAUDE.md -> „Dane wejściowe").

    Do czego:
    Leży w `model/`, a nie przy czytniku, który go wypełnia, bo jest WEJŚCIOWĄ połową kontraktu,
    którego wyjściem jest `ParsedTicket`: każdy czytnik źródła wypełnia ten sam kształt. Obok
    `ticket_parsed.py` obie strony tego przekształcenia czyta się razem.

    Flow:
        1. Czytnik (dziś `parser_ticket_raw.load_raw_ticket()`, przy masowym imporcie także
           wariant SQL) czyta jeden rekord źródłowy i wypełnia ten model, zdejmując HTML.
        2. `as_thread()` robi z niego tekst wątku: czyta go parser, a po anonimizacji trafia on
           do tabeli wyszukiwania tekstowego.
        3. `ticket_id` i `date` idą wprost do `ParsedTicket` — pochodzą ze źródła, nigdy z modelu,
           więc LLM nie ma czego w nich pomylić.
    """

    ticket_id: str  = Field(examples=["33644"])
    date:      Date = Field(examples=["2026-06-23"])
    # Czytana ze źródła, ale celowo NIE mapowana na pole karty: `category` wypadło ze schematu.
    # Zostaje tutaj, bo „Automat mailowy" wyznacza rekordy, w których cytowaną historię maili
    # trzeba wyczyścić przed parsowaniem (CLAUDE.md -> „Mapowanie tabel").
    category:  str  = Field(examples=["Automat mailowy", "Błąd"])
    subject:   str  = Field(examples=["ESOD Dokus - Zakończona aktualizacja środowiska testowego"])
    body:      str  = Field(examples=["Dzień dobry, po aktualizacji nie działa wysyłka…"])

    comments: list[RawComment] = Field(default_factory=list)

    def as_thread(self) -> str:
        """
        Description:
        Robi ze zgłoszenia tekst wątku. Komentarze zostają w kolejności źródła, bo ten korpus
        czyta się jak chronologię — najcenniejsze zdanie bywa w ostatnim komentarzu, czasem
        napisanym po zamknięciu zgłoszenia.

        Autor i typ komentarza są podpisane, ale nic z nich nie wynika: prompt każe modelowi
        ważyć treść ponad etykiety, więc ich ukrycie zabrałoby kontekst, a zaufanie im
        powtórzyłoby udokumentowaną wadę tej bazy.

        Example args:
            (brak)

        Example result:
            "ZGŁOSZENIE 33644 z 2026-06-23\\nTemat: Błąd wysyłki\\n\\nOPIS ZGŁASZAJĄCEGO:\\n…"
        """
        parts = [
            f"ZGŁOSZENIE {self.ticket_id} z {self.date.isoformat()}",
            f"{SUBJECT_PREFIX}{self.subject}",
            "",
            "OPIS ZGŁASZAJĄCEGO:",
            self.body or "(brak opisu)",
        ]

        # Powiedziane wprost zamiast przemilczane: wątek bez żadnego komentarza to znana klasa
        # rekordów bez wiedzy i model ma widzieć, że na taki patrzy.
        if not self.comments:
            parts += ["", "(brak komentarzy w wątku)"]

        for index, comment in enumerate(self.comments, start=1):
            parts += [
                "",
                f"KOMENTARZ {index} — {comment.role}, {comment.created_at} (typ: {comment.kind}):",
                comment.body or "(pusty komentarz)",
            ]

        return "\n".join(parts)

    @staticmethod
    def subject_of_thread(
        thread: str,  # np. "ZGŁOSZENIE 33644 z 2026-06-23\nTemat: Błąd wysyłki\n\nOPIS…"
    ) -> str:
        """
        Description:
        Wycina temat z tekstu wątku — odwrotność linii z tematem w `as_thread()`. Potrzebne tam,
        gdzie wątek przeszedł anonimizację jako jeden tekst: tematu nie wolno już wtedy brać ze
        źródła, bo ten jest sprzed anonimizacji.

        Example args:
            thread="ZGŁOSZENIE 33644 z 2026-06-23\\nTemat: Błąd wysyłki\\n\\nOPIS…"

        Example result:
            "Błąd wysyłki"

        Raises:
            ValueError: w tekście nie ma linii z tematem
        """
        # Pierwsza taka linia jest nasza: nagłówek wątku stoi przed treścią zgłoszenia.
        for line in thread.splitlines():
            if line.startswith(SUBJECT_PREFIX):
                return line.removeprefix(SUBJECT_PREFIX).strip()

        raise ValueError(f"wątek bez linii „{SUBJECT_PREFIX.strip()}” — nie ma skąd wziąć tematu")
