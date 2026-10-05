from pydantic import BaseModel, Field

from app.core_model.tickets.quality_report import QualityReport


class TicketsIndexReport(BaseModel):
    """
    Description:
    Co zrobił jeden przebieg indeksacji zgłoszeń: ile artefaktów wczytał, ile odrzucił filtr
    jakości i dlaczego, i ile punktów trafiło do Qdranta.

    Do czego:
    Przebieg indeksacji to jedyna chwila, w której na korpus patrzy się jako na całość, więc musi
    powiedzieć, co wyrzucił — filtr, który po cichu przepoławia indeks, wygląda dokładnie jak
    działający. Rozbicie per powód niesie wbudowany `QualityReport`; ten model dokłada to, co
    działo się wokół niego.

    `read` liczy artefakty, które poprawnie się wczytały, a nie pliki na dysku: wadliwe pliki
    raportuje osobno `helpdesk tickets validate`, a zmieszanie obu liczb schowałoby zepsuty
    artefakt za statystyką filtru.
    """

    read:     int           = Field(examples=[200])
    indexed:  int           = Field(examples=[171])
    filtered: QualityReport = Field(default_factory=QualityReport)
    # Uwagi, które przebieg chce pokazać operatorowi — dziś kontrola odsetka odrzuceń, czyli
    # sposób, w jaki zamilkły filtr daje o sobie znać (`filter_ticket_quality.drop_rate_warning`).
    warnings: list[str]     = Field(default_factory=list)

    @property
    def dropped(self) -> int:
        """
        Description:
        Ile artefaktów odrzucił filtr.

        Example args:
            (brak)

        Example result:
            29
        """
        return len(self.filtered.dropped)
