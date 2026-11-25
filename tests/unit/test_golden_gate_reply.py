"""
Description:
Wycinanie wiadomości konsultanta z tekstu wątku i skrót wiadomości z helpera zestawu bramki
wysyłki (`tests/_helpers/golden_gate_reply/`). Z nich test bramki na żywym modelu składa wejście
i sprawdza, że etykiety opisują ten tekst, więc błąd tu dałby pomiar na innej wiadomości, niż
widzieli oceniający.
"""

from datetime import date

import pytest

from app.core_model.tickets.raw_comment import RawComment
from app.core_model.tickets.raw_ticket import RawTicket
from tests._helpers.golden_gate_reply import consultant_message, message_digest


def three_comment_thread() -> str:
    """
    Description:
    Wątek zgłoszenia z trzema komentarzami, złożony tak samo jak wątki korpusu: konsultant,
    klient, konsultant. Pierwsza wiadomość ma w środku pustą linię, a ostatnia kończy wątek.

    Example args:
        (brak)

    Example result:
        "ZGŁOSZENIE 90002 z 2026-01-02\nTemat: Nie działa wysyłka\n\nOPIS ZGŁASZAJĄCEGO:\n…"
    """
    comments = [
        RawComment(kind="zwyczajny", role="konsultant", created_at="2026-01-02 10:00",
                   body="Dzień dobry,\n\nproszę o zrzut ekranu."),
        RawComment(kind="zwyczajny", role="klient", created_at="2026-01-03 11:00",
                   body="W załączeniu."),
        RawComment(kind="rozwiazanie", role="konsultant", created_at="2026-01-04 12:00",
                   body="Poprawka wgrana.\nPozdrawiam"),
    ]
    ticket = RawTicket(
        ticket_id = "90002",
        date      = date(2026, 1, 2),
        category  = "Błąd",
        subject   = "Nie działa wysyłka",
        body      = "Opis.",
        comments  = comments,
    )

    return ticket.as_thread()


@pytest.mark.parametrize(
    ("comment", "expected"),
    [
        pytest.param(1, "Dzień dobry,\n\nproszę o zrzut ekranu.", id="pierwszy-z-pusta-linia"),
        pytest.param(3, "Poprawka wgrana.\nPozdrawiam", id="ostatni-w-watku"),
    ],
)
def test_the_message_is_the_comment_body_only(comment: int, expected: str) -> None:
    """Sprawdza, czy z wątku wychodzi dokładnie treść wskazanego komentarza konsultanta: bez
    nagłówka, bez pustej linii przed następnym komentarzem, z pustymi liniami wewnątrz treści,
    także gdy komentarz kończy wątek.

    Wyłapuje wycinanie, które dokleja nagłówek albo kawałek następnego komentarza, gubi
    akapit albo ucina ostatni komentarz: bramka oceniałaby inny tekst, niż widzieli
    oceniający, a słowo z cudzego komentarza mogłoby dać fałszywy alarm."""
    assert consultant_message(three_comment_thread(), comment) == expected


@pytest.mark.parametrize(
    ("comment", "problem"),
    [
        pytest.param(2, "klient", id="komentarz-klienta"),
        pytest.param(4, "3 komentarzy", id="numer-za-duzy"),
        pytest.param(0, "3 komentarzy", id="numer-zero"),
    ],
)
def test_only_an_existing_consultant_comment_is_a_message(comment: int, problem: str) -> None:
    """Sprawdza, czy wycinanie odmawia błędem, gdy wpis wskazuje komentarz klienta albo numer,
    którego w wątku nie ma.

    Wyłapuje wpis, który po cichu mierzyłby bramkę na wypowiedzi klienta (bramka ocenia
    wiadomości do klienta) albo na pustym tekście po pomyłce w numerze."""
    with pytest.raises(ValueError, match=problem):
        consultant_message(three_comment_thread(), comment)


def test_a_gap_in_comment_numbers_is_an_error() -> None:
    """Sprawdza, czy wycinanie odmawia, gdy numery nagłówków komentarzy nie idą po kolei.

    Wyłapuje wątek złożony inaczej niż przez `RawTicket.as_thread()`, w którym numer wpisu
    wskazałby inny komentarz, niż oceniano."""
    thread = three_comment_thread().replace("KOMENTARZ 2 — ", "KOMENTARZ 5 — ")

    with pytest.raises(ValueError, match="po kolei"):
        consultant_message(thread, 1)


def test_the_digest_is_fixed_for_a_known_text() -> None:
    """Sprawdza, czy skrót znanej wiadomości ma zapisaną wartość.

    Wyłapuje zmianę algorytmu albo długości skrótu: wszystkie wpisy zestawu przestałyby się
    zgadzać z korpusem, a test spójności zgłosiłby 179 zmienionych wiadomości zamiast jednej
    zmiany w helperze."""
    assert message_digest("Dzień dobry.") == "a2d4c66de139ad2f"
