import dataclasses


@dataclasses.dataclass(frozen=True)
class QuestionsCase:
    """Jedna sprawa z zestawu: zgłoszenie i to, czy po jego faktach pytania są potrzebne."""

    case_id:    str   # np. "w01"
    phenomenon: str   # np. "odpowiedzi klienta w wątku rozstrzygają"
    text:       str   # zgłoszenie w kształcie `RawTicket.as_thread()`
    questions:  bool  # np. False — fakty rozstrzygają, oczekiwane `text: null`

    @property
    def label(self) -> str:
        """
        Description:
        Nazwa sprawy w raporcie: identyfikator i zjawisko.

        Example args:
            (brak)

        Example result:
            "w01 odpowiedzi klienta w wątku rozstrzygają"
        """
        return f"{self.case_id} {self.phenomenon}"
