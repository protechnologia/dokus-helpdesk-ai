from datetime import date as Date

import pytest

from app.core_model.tickets.raw_comment import RawComment
from app.core_model.tickets.raw_ticket import RawTicket


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
    """Sprawdza, czy tekst wątku zbudowany ze zgłoszenia zawiera nagłówek z numerem i datą
    („ZGŁOSZENIE 33644 z 2026-06-23"), temat i opis zgłaszającego.

    Wyłapuje wątek, który gubi któryś z tych elementów: ten tekst jest materiałem dla modelu
    parsującego, więc czego w nim zabraknie, tego model nie zobaczy."""
    thread = _ticket().as_thread()

    assert "ZGŁOSZENIE 33644 z 2026-06-23" in thread
    assert "Błąd wysyłki"                  in thread
    assert "Nie działa wysyłka"            in thread


def test_thread_labels_comment_author_and_type():
    """Sprawdza, czy komentarz w tekście wątku ma podpisaną rolę autora (tu `konsultant`) i typ
    (tu `rozwiazanie`) oraz niesie swoją treść.

    Wyłapuje wątek bez tych etykiet albo bez treści komentarza: prompt każe modelowi ważyć
    treść ponad etykietami, ale ich ukrycie zabrałoby mu kontekst, kto i w jakiej roli pisał."""
    thread = _ticket().as_thread()

    assert "konsultant" in thread
    assert "rozwiazanie" in thread
    assert "Wygenerowano certyfikat." in thread


def test_thread_keeps_comment_order():
    """Sprawdza, czy dwa komentarze stoją w tekście wątku w kolejności ze źródła: komentarz
    o treści „PIERWSZY" przed komentarzem o treści „DRUGI".

    Wyłapuje przestawienie komentarzy: wątek czyta się jak chronologię, a najcenniejsze zdanie
    bywa w ostatnim komentarzu, więc inna kolejność zmieniłaby obraz sprawy."""
    thread = _ticket(comments=[
        RawComment(kind="zwyczajny", role="klient",
                   created_at="2026-06-23 12:00:00", body="PIERWSZY"),
        RawComment(kind="zwyczajny", role="konsultant",
                   created_at="2026-06-23 13:00:00", body="DRUGI"),
    ]).as_thread()

    assert thread.index("PIERWSZY") < thread.index("DRUGI")


def test_thread_says_when_there_are_no_comments():
    """Sprawdza, czy wątek zgłoszenia bez komentarzy mówi to wprost, osobną linią o treści
    „(brak komentarzy w wątku)".

    Wyłapuje przemilczenie braku komentarzy: wątek bez żadnego komentarza to znany rodzaj
    zgłoszeń bez wiedzy i model ma widzieć, że na taki patrzy."""
    assert "(brak komentarzy w wątku)" in _ticket(comments=[]).as_thread()


def test_thread_says_when_the_body_is_empty():
    """Sprawdza, czy zgłoszenie z pustym opisem dostaje w tekście wątku jawny znacznik
    „(brak opisu)".

    Wyłapuje wątek, w którym w miejscu opisu nie ma nic: w prompcie zostałoby puste miejsce,
    z którego nie wynika, że zgłaszający niczego nie opisał."""
    assert "(brak opisu)" in _ticket(body="").as_thread()


def test_the_subject_is_cut_back_out_of_the_thread() -> None:
    """Sprawdza, czy z tekstu wątku da się z powrotem wyciąć temat: wątek zgłoszenia o temacie
    „Błąd wysyłki przez ePUAP" oddaje dokładnie ten temat.

    Wyłapuje rozjazd między zapisem tematu w wątku a jego odczytem: tabela wyszukiwania bierze
    tytuł właśnie stąd, bo anonimizację przechodzi cały wątek, a temat ze źródła jest sprzed
    anonimizacji."""
    thread = _ticket(subject="Błąd wysyłki przez ePUAP").as_thread()

    assert RawTicket.subject_of_thread(thread) == "Błąd wysyłki przez ePUAP"


def test_a_subject_line_inside_the_content_is_not_the_subject() -> None:
    """Sprawdza, czy linia zaczynająca się od „Temat:" w opisie zgłaszającego nie jest brana za
    temat: wynikiem jest temat z nagłówka wątku („Błąd wysyłki"), bo stoi pierwszy.

    Wyłapuje odczyt, który bierze ostatnią albo dowolną taką linię: treść wpisana przez
    zgłaszającego podmieniłaby wtedy tytuł zgłoszenia w tabeli wyszukiwania."""
    thread = _ticket(body="Temat: to nie jest temat").as_thread()

    assert RawTicket.subject_of_thread(thread) == "Błąd wysyłki"


def test_a_text_without_the_subject_line_is_refused() -> None:
    """Sprawdza, czy tekst bez linii z tematem, czyli taki, który nie jest wątkiem, kończy się
    wyjątkiem `ValueError` wspominającym o temacie.

    Wyłapuje odczyt, który w takim przypadku oddaje pusty albo zgadnięty tytuł: zgłoszenie
    trafiłoby do tabeli wyszukiwania z tytułem, którego w źródle nie było."""
    with pytest.raises(ValueError, match="Temat"):
        RawTicket.subject_of_thread("Dzień dobry, od wczoraj nie działa wysyłka.")
