from pydantic import BaseModel, Field

from app.core_model.dicts.resolution_class import ResolutionClass


class ResolutionVocabulary(BaseModel):
    """
    Description:
    Konfigurowalny słownik rodzajów rozstrzygnięć i wersja, w której go wczytano.

    Dlaczego wersjonowany: słownik jest wstawiany do promptu PARSUJĄCEGO, więc jego edycja zmienia
    znaczenie przyszłych artefaktów. Każdy `ParsedTicket` zapisuje wersję, którą powstał, więc
    późniejsza edycja nie unieważnia po cichu `data/unsafe/parsed/` (zasada 7), a ponowne
    parsowanie może być wybiórcze zamiast całkowitego.

    Celowo NIE Enum w kodzie: to, gdzie helpdesk stawia granicę między „zmieniliśmy coś
    w systemie" a „klient działa u siebie", wynika z tego, jak pracuje dana organizacja,
    i w następnej znaczy co innego — więc zestaw należy do danych klienta, nie do naszego kodu.
    Czyta go `core_service/loader_dict_resolution.py`; to szew, który p. 29 podmienia na SQL.
    """

    version: int                     = Field(examples=[1])
    classes: list[ResolutionClass]

    def names(self) -> list[str]:
        """
        Description:
        Oddaje same identyfikatory, w kolejności deklaracji — z nimi porównuje walidator i je
        prompt wymienia jako dozwolone odpowiedzi.

        Example args:
            (brak)

        Example result:
            ["naprawione", "bez_zmian_w_systemie", "brak"]
        """
        return [entry.name for entry in self.classes]
