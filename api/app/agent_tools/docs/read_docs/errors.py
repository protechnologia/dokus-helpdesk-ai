from app.agent_tools.errors import ToolCallError


class UnknownSectionError(ToolCallError):
    """
    Description:
    Agent poprosił o sekcję, której w dokumentacji nie ma — literówka w identyfikatorze albo
    identyfikator wymyślony.

    Błąd, a nie krótsza lista: odczyt trzech sekcji zamiast czterech wygląda dokładnie jak
    poprawny, a odpowiedź oparta na niepełnym materiale nie nosi po tym śladu. Komunikat wraca
    do modelu jako wynik narzędzia, żeby mógł poprawić wywołanie (stąd `ToolCallError`), więc
    wymienia nieznane identyfikatory — to nazwy sekcji, nie dane klienta.
    """

    def __init__(
        self,
        section_ids: list[str],  # np. ["adm-kancelaria-edoreczenie"]
    ):
        """
        Description:
        Zapamiętuje nieznane identyfikatory i składa z nich komunikat.

        Example args:
            section_ids=["adm-kancelaria-edoreczenie"]

        Example result:
            UnknownSectionError("nieznane sekcje dokumentacji: adm-kancelaria-edoreczenie")
        """
        self.section_ids = section_ids

        super().__init__(f"nieznane sekcje dokumentacji: {', '.join(section_ids)}")
