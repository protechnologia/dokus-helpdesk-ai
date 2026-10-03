from datetime import date as Date

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
