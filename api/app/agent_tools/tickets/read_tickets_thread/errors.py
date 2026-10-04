class UnknownTicketError(Exception):
    """
    Description:
    Agent poprosił o wątek zgłoszenia, którego w bazie nie ma — literówka w numerze albo numer
    wymyślony.

    Błąd, a nie krótsza lista: odczyt trzech wątków zamiast czterech wygląda dokładnie jak
    poprawny, a odpowiedź oparta na niepełnym materiale nie nosi po tym śladu. Komunikat wraca
    do modelu jako wynik narzędzia, żeby mógł poprawić wywołanie (p. 10), więc wymienia nieznane
    numery — to identyfikatory, nie dane klienta.

    Inaczej niż w `read_tickets_card`: wątek ma każde zgłoszenie, więc jego brak znaczy zły
    numer, a karty może nie być dla zgłoszenia, które istnieje.
    """

    def __init__(
        self,
        ticket_ids: list[str],  # np. ["90019"]
    ):
        """
        Description:
        Zapamiętuje nieznane numery i składa z nich komunikat.

        Example args:
            ticket_ids=["90019"]

        Example result:
            UnknownTicketError("nieznane zgłoszenia: 90019")
        """
        self.ticket_ids = ticket_ids

        super().__init__(f"nieznane zgłoszenia: {', '.join(ticket_ids)}")
