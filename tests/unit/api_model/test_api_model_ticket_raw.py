from datetime import date as Date

import pytest

from app.model.ticket_raw import RawTicket
from app.model.ticket_raw_comment import RawComment


def _ticket(**overrides) -> RawTicket:
    """
    Description:
    Builds a RawTicket for the thread-rendering tests, without touching the filesystem.

    Example args:
        overrides={"comments": []}

    Example result:
        RawTicket(ticket_id="33644", date=date(2026, 6, 23), …)
    """
    values = {
        "ticket_id": "33644",
        "date":      Date(2026, 6, 23),
        "category":  "Błąd",
        "subject":   "Błąd wysyłki",
        "body":      "Nie działa wysyłka",
        "comments":  [
            RawComment(
                kind       = "rozwiazanie",
                role       = "konsultant",
                created_at = "2026-06-23 12:01:21",
                body       = "Wygenerowano certyfikat.",
            )
        ],
    }
    values.update(overrides)

    return RawTicket(**values)


def test_thread_carries_identity_subject_and_body():
    """Wątek → numer, data, temat i opis; to jest materiał dla promptu."""
    thread = _ticket().as_thread()

    assert "ZGŁOSZENIE 33644 z 2026-06-23" in thread
    assert "Błąd wysyłki"                  in thread
    assert "Nie działa wysyłka"            in thread


def test_thread_labels_comment_author_and_type():
    """Komentarz → widoczna rola i typ; prompt każe modelowi ważyć treść ponad etykietami."""
    thread = _ticket().as_thread()

    assert "konsultant" in thread
    assert "rozwiazanie" in thread
    assert "Wygenerowano certyfikat." in thread


def test_thread_keeps_comment_order():
    """Kilka komentarzy → kolejność źródłowa; najcenniejsze zdanie bywa w ostatnim."""
    thread = _ticket(comments=[
        RawComment(kind="zwyczajny", role="klient",
                   created_at="2026-06-23 12:00:00", body="PIERWSZY"),
        RawComment(kind="zwyczajny", role="konsultant",
                   created_at="2026-06-23 13:00:00", body="DRUGI"),
    ]).as_thread()

    assert thread.index("PIERWSZY") < thread.index("DRUGI")


def test_thread_says_when_there_are_no_comments():
    """Wątek bez komentarzy → powiedziane wprost, bo to znana klasa rekordów bez wiedzy."""
    assert "(brak komentarzy w wątku)" in _ticket(comments=[]).as_thread()


def test_thread_says_when_the_body_is_empty():
    """Pusty opis → jawny znacznik zamiast pustego miejsca w prompcie."""
    assert "(brak opisu)" in _ticket(body="").as_thread()


def test_the_subject_is_cut_back_out_of_the_thread() -> None:
    """Tekst wątku → temat z linii, którą zapisało `as_thread()`: tak tabela wyszukiwania dostaje
    tytuł po anonimizacji całego wątku."""
    thread = _ticket(subject="Błąd wysyłki przez ePUAP").as_thread()

    assert RawTicket.subject_of_thread(thread) == "Błąd wysyłki przez ePUAP"


def test_a_subject_line_inside_the_content_is_not_the_subject() -> None:
    """Linia „Temat:" także w opisie zgłaszającego → temat z nagłówka wątku, bo ten stoi
    pierwszy."""
    thread = _ticket(body="Temat: to nie jest temat").as_thread()

    assert RawTicket.subject_of_thread(thread) == "Błąd wysyłki"


def test_a_text_without_the_subject_line_is_refused() -> None:
    """Tekst, który nie jest wątkiem → ValueError: tytułu źródła nie wolno zgadywać."""
    with pytest.raises(ValueError, match="Temat"):
        RawTicket.subject_of_thread("Dzień dobry, od wczoraj nie działa wysyłka.")
