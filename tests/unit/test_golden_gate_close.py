"""
Description:
Ucięcie wątku na zamknięciu i skrót uciętego tekstu z helpera zestawu bramki zamknięcia
(`tests/_helpers/golden_gate_close/`). Z nich test bramki na żywym modelu składa wejście
i sprawdza, że etykiety opisują ten tekst, więc błąd tu dałby pomiar na innym wątku, niż
widzieli oceniający.
"""

from datetime import date

import pytest

from app.core_model.tickets.raw_comment import RawComment
from app.core_model.tickets.raw_ticket import RawTicket
from tests._helpers.golden_gate_close import thread_at_close, thread_digest


def three_comment_thread() -> str:
    """
    Description:
    Wątek zgłoszenia z trzema komentarzami, złożony tak samo jak wątki korpusu.

    Example args:
        (brak)

    Example result:
        "ZGŁOSZENIE 90001 z 2026-01-02\nTemat: Nie działa wysyłka\n\nOPIS ZGŁASZAJĄCEGO:\n…"
    """
    # Trzeci komentarz klient napisał po zamknięciu: ucięcie po dwóch ma go zdjąć.
    comments = [
        RawComment(kind="zwyczajny", role="konsultant", created_at="2026-01-02 10:00",
                   body="Pytanie."),
        RawComment(kind="rozwiazanie", role="konsultant", created_at="2026-01-03 11:00",
                   body="Rozwiązanie."),
        RawComment(kind="zwyczajny", role="klient", created_at="2026-01-09 12:00",
                   body="Po zamknięciu."),
    ]
    ticket = RawTicket(
        ticket_id = "90001",
        date      = date(2026, 1, 2),
        category  = "Błąd",
        subject   = "Nie działa wysyłka",
        body      = "Opis.",
        comments  = comments,
    )

    return ticket.as_thread()


def test_the_cut_keeps_comments_up_to_the_closing_one() -> None:
    """Sprawdza, czy ucięcie po dwóch komentarzach z trzech zostawia opis i dwa pierwsze
    komentarze, a nagłówek i treść trzeciego znikają.

    Wyłapuje ucięcie o jeden komentarz za wcześnie albo za późno: bramka oceniałaby wątek bez
    komentarza zamykającego albo z odpowiedzią klienta napisaną po zamknięciu."""
    cut = thread_at_close(three_comment_thread(), 2)

    assert cut.endswith("Rozwiązanie.")
    assert "KOMENTARZ 2 — " in cut
    assert "KOMENTARZ 3 — " not in cut
    assert "Po zamknięciu." not in cut


def test_zero_comments_leave_the_description_and_all_comments_leave_the_thread() -> None:
    """Sprawdza, czy przy zerze komentarzy zostaje sam nagłówek z opisem, a przy wszystkich
    wątek wraca znak w znak.

    Wyłapuje ucięcie, które przy zgłoszeniu zamkniętym bez komentarza zostawia pierwszy
    komentarz, albo takie, które przy pełnym wątku obcina jego koniec."""
    thread = three_comment_thread()

    assert thread_at_close(thread, 0).endswith("Opis.")
    assert "KOMENTARZ" not in thread_at_close(thread, 0)
    assert thread_at_close(thread, 3) == thread


def test_more_comments_than_the_thread_has_is_refused() -> None:
    """Sprawdza, czy ucięcie po większej liczbie komentarzy, niż ma wątek, kończy się błędem.

    Wyłapuje ciche oddanie całego wątku, gdy zestaw i korpus się rozjechały: bramka oceniałaby
    inny wątek, niż widzieli oceniający, a skrót by tego nie pokazał."""
    with pytest.raises(ValueError):
        thread_at_close(three_comment_thread(), 4)


def test_the_thread_digest_keeps_its_golden_value() -> None:
    """Sprawdza, czy skrót uciętego wątku ma zapisaną wartość dla znanego tekstu i czy zmiana
    jednego znaku go zmienia.

    Wyłapuje zmianę sposobu liczenia skrótu: każdy wpis zestawu przestałby się zgadzać
    z zapisanym skrótem, a test spójności padałby bez zmiany danych."""
    text = "ZGŁOSZENIE 1 z 2026-01-02\nTemat: T"

    assert thread_digest(text) == "46266d8496d232c3"
    assert thread_digest(text + " ") != thread_digest(text)
