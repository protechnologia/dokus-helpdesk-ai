class UnknownTicketError(Exception):
    """
    Description:
    Agent poprosił o wątek zgłoszenia, którego w bazie nie ma — literówka w numerze albo numer
    wymyślony.

    Błąd, a nie pusty wynik: komunikat wraca do modelu jako wynik narzędzia, żeby mógł poprawić
    wywołanie (p. 10), więc wymienia nieznany numer — to identyfikator, nie dane klienta.

    Inaczej niż w `read_tickets_card`: wątek ma każde zgłoszenie, więc jego brak znaczy zły
    numer, a karty może nie być dla zgłoszenia, które istnieje.
    """

    def __init__(
        self,
        ticket_id: str,  # np. "90019"
    ):
        """
        Description:
        Zapamiętuje nieznany numer i składa z niego komunikat.

        Example args:
            ticket_id="90019"

        Example result:
            UnknownTicketError("nieznane zgłoszenie: 90019")
        """
        self.ticket_id = ticket_id

        super().__init__(f"nieznane zgłoszenie: {ticket_id}")
