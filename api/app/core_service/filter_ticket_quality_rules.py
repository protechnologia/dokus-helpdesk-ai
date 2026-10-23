"""
Description:
Lista reguł filtra jakości, który przy indeksacji (`helpdesk tickets index`) decyduje, czy
sparsowane zgłoszenie niesie jakąkolwiek wiedzę i warto je wpuścić do Qdranta.

| reguła       | odpala, gdy                                                         |
|--------------|---------------------------------------------------------------------|
| `not_useful` | model parsujący ocenił kartę jako nieprzydatną (`useful` = false)   |

Sam plik niczego nie odrzuca. Robi to orkiestrator `filter_ticket_quality.py`, który iteruje po
krotce `RULES` z końca pliku i składa werdykt oraz raport dla `indexer_tickets`. Reguła dostaje
całą kartę i oddaje dowód do raportu albo None. Dołożenie reguły to dopisanie funkcji, wpisu
w `RULES` i wiersza w tabelce; testy parametryzują się po tej krotce.

O czym pamiętać przy zmianach:

- Ocenę wydaje model, który widział cały wątek, a filtr widzi tylko kartę. Sygnały braku wiedzy
  („omówione telefonicznie”, „instrukcja w załączeniu”, echo prośby „usunięto”) przy parsowaniu
  giną, więc reguła po tekście karty ich nie odtworzy.
- Reguła stoi na regule pola `useful` w opisie narzędzia `respond_parse_ticket`: zmiana tamtej
  reguły jest zmianą filtru, choćby nie tknęła tego pliku. Po niej przelicza się test filtra na
  korpusie odniesienia.
"""

from app.core_model.tickets.parsed_ticket import ParsedTicket


def not_useful(
    ticket: ParsedTicket,  # np. ParsedTicket(ticket_id="34071", useful=False, …)
) -> str | None:
    """
    Description:
    Odpala, gdy model parsujący ocenił kartę jako nieprzydatną przy innej sprawie. Dowodem do
    raportu jest uzasadnienie modelu (`useful_reason`), żeby każde odrzucenie dało się sprawdzić;
    karta przydatna przechodzi.

    Na 200 kartach odniesienia (golden200, `gpt-6.1-sol`, 2026-10-23) reguła odrzuca 59 z 65
    rekordów oznaczonych jako bez wiedzy i żadnego ze 135 dobrych.

    Example args:
        ticket=ParsedTicket(ticket_id="34071", useful=False,
                            useful_reason="Wątek potwierdza jedynie usunięcie sprawy.", …)

    Example result:
        "Wątek potwierdza jedynie usunięcie sprawy."

    Example args:
        ticket=ParsedTicket(ticket_id="24661", solution="brak", cause="Miniona data ważności…",
                            useful=True, …)

    Example result:
        None — przyczyna w `cause` to wiedza, choć rozwiązania nie opisano
    """
    if ticket.useful:
        return None

    return ticket.useful_reason


# Reguły w kolejności raportu; po tej krotce iterują orkiestrator i testy.
# Jedna celowo: dawna reguła po frazie „brak” w `solution` (`no_resolution`) odrzucała też karty
# z przyczyną w `cause`, a karty bez wiedzy z niepustym rozwiązaniem przepuszczała.
RULES = (
    not_useful,
)
