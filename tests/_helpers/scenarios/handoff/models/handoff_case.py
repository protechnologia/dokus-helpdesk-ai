import dataclasses


@dataclasses.dataclass(frozen=True)
class HandoffCase:
    """Jedna sprawa przekazania z zestawu: zgłoszenie i to, co ma się z nim stać."""

    case_id:    str              # np. "h01"
    phenomenon: str              # np. "ostrzeżenie w wątku ma dotrzeć do klienta"
    text:       str              # zgłoszenie jak z `as_thread()`, np. "ZGŁOSZENIE 90304 z…"
    kept:       tuple[str, ...]  # fakty, które mają stać w wiadomości, np. ("ePUAP",)
    warning:    tuple[str, ...]  # rdzenie ostrzeżenia, wystarczy jeden, np. ("nie ponawia",)
    tempting:   tuple[str, ...]  # pułapki: dopiski, których nie ma w wątku, np. ("wygas",)

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa sprawy w raporcie: identyfikator i zjawisko.

        Example args:
            (brak)

        Example result:
            "h04 ostrzeżenie w wątku ma dotrzeć do klienta"
        """
        return f"{self.case_id} {self.phenomenon}"
