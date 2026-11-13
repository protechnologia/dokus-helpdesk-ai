"""
Description:
Układ katalogu korpusu zgłoszeń: gdzie leżą karty, wątki po anonimizacji i surowe zgłoszenia
z obu źródeł. Katalog główny podaje konfiguracja (`TICKETS_CORPUS_DIR`), a nazwy podkatalogów
stoją tutaj, żeby komendy `helpdesk tickets`, zapis zamkniętego zgłoszenia (p. 30) i masowy
import (p. 31) trafiały w te same miejsca. Czyta go `Settings.tickets_corpus()`.

| podkatalog    | co w nim                                           | dane osobowe |
|---------------|----------------------------------------------------|--------------|
| `cards/`      | karty, `<numer>.json`                              | nie          |
| `anonymized/` | wątki po anonimizacji, `<numer>.txt`               | nie          |
| `raw-db/`     | eksport zrzutu bazy, `zgloszenie-<numer>.json`     | tak          |
| `raw-route/`  | zgłoszenia, które przyszły trasą, jako `RawTicket` | tak          |

Raporty masowego importu leżą w samym katalogu korpusu, po jednym na przebieg:
`import-<data i godzina startu>.json` (`import_report_path()`), same numery i liczby.

O czym pamiętać: indeksy odbudowują się z `cards/` i `anonymized/` (zasada 8), więc tych dwóch
podkatalogów nie wolno kasować; surowe zgłoszenia służą tylko ponownej anonimizacji.
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class TicketsCorpus(BaseModel):
    """
    Description:
    Katalog korpusu zgłoszeń z nazwanymi podkatalogami na każdy etap: surowe zgłoszenie, wątek po
    anonimizacji i karta.
    """

    root: Path = Field(examples=[Path("/code/data/unsafe/corpus")])

    @property
    def cards_dir(self) -> Path:
        """
        Description:
        Zwraca katalog kart — z niego komendy `helpdesk tickets` budują indeks Qdranta.

        Example args:
            (brak)

        Example result:
            Path("/code/data/unsafe/corpus/cards")
        """
        return self.root / "cards"

    @property
    def anonymized_dir(self) -> Path:
        """
        Description:
        Zwraca katalog wątków po anonimizacji — z niego odbudowuje się tabela wątków w Postgresie.

        Example args:
            (brak)

        Example result:
            Path("/code/data/unsafe/corpus/anonymized")
        """
        return self.root / "anonymized"

    @property
    def raw_db_dir(self) -> Path:
        """
        Description:
        Zwraca katalog eksportu zrzutu bazy, który zdejmuje `scripts/export_raw_tickets.py`.

        Example args:
            (brak)

        Example result:
            Path("/code/data/unsafe/corpus/raw-db")
        """
        return self.root / "raw-db"

    @property
    def raw_route_dir(self) -> Path:
        """
        Description:
        Zwraca katalog surowych zgłoszeń, które przyszły trasą zamknięcia zgłoszenia.

        Example args:
            (brak)

        Example result:
            Path("/code/data/unsafe/corpus/raw-route")
        """
        return self.root / "raw-route"

    def import_report_path(
        self,
        started_at: datetime,  # np. datetime(2026, 11, 13, 10, 15, tzinfo=UTC)
    ) -> Path:
        """
        Description:
        Zwraca ścieżkę raportu przebiegu masowego importu, który ruszył o podanej chwili. Nazwa
        zaczyna się od daty i godziny, więc raporty układają się po kolei.

        Example args:
            started_at=datetime(2026, 11, 13, 10, 15, tzinfo=UTC)

        Example result:
            Path("/code/data/unsafe/corpus/import-2026-11-13T10-15-00.json")
        """
        return self.root / f"import-{started_at:%Y-%m-%dT%H-%M-%S}.json"
