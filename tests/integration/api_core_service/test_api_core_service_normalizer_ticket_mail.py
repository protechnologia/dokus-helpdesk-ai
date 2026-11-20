"""
Description:
Normalizer wątków kanału „Automat mailowy” (`core_service/normalizer_ticket_mail.py`) na
słowniku zmyślonym z `data/safe/mail/` i zmyślonych wątkach, z których ten słownik powstał:
druga kopia maila, cytat, stopka dostawcy, odwołanie do obrazka i role z podpisów (p. 32).
"""

from pathlib import Path

import pytest

from app.core_service.loader_mail_dictionary import MailDictionaryConfigError
from app.core_service.normalizer_ticket_mail import (
    CLIENT_ROLE,
    VENDOR_ROLE,
    MailNormalizer,
    normalize_mail_ticket,
)
from tests._helpers.mail import (
    SAFE_MAIL_DIR,
    mail_ticket,
    safe_mail_ticket,
    safe_templates,
    safe_vendor_names,
)
from tests._helpers.mail.samples import sample_cleaned_thread


def test_a_mail_thread_comes_back_cleaned_with_authors() -> None:
    """Sprawdza, czy zmyślony wątek z maila klienta i odpowiedzi dostawcy wraca w całości taki,
    jak zapisuje go próbka: opis bez drugiej kopii, odpowiedź bez stopki, obrazka i cytatu,
    klauzula RODO urzędu przy pierwszym wystąpieniu, a w nagłówkach autorzy z podpisów.

    Wyłapuje każdą zmianę wyniku na wątku, na którym przegląd ustalał metodę: zgubioną nową
    treść, zostawiony cytat albo stopkę i role przepisane z bazy zamiast z podpisów."""
    ticket = normalize_mail_ticket(safe_mail_ticket(41101), safe_templates(), safe_vendor_names())

    assert ticket.as_thread() == sample_cleaned_thread()


def test_the_vendor_footer_disappears_at_its_first_occurrence() -> None:
    """Sprawdza, czy z zapowiedzi dostawcy, jedynej wiadomości w swoim wątku, znika stopka
    poufności ze słownika szablonów, zostaje treść z podpisem, a opis ma autora `konsultant`.

    Wyłapuje słownik szablonów, który nie działa: stopka nie ma w tym wątku wcześniejszego
    wystąpienia, więc same powtórzenia by jej nie zdjęły."""
    ticket = normalize_mail_ticket(safe_mail_ticket(41102), safe_templates(), safe_vendor_names())

    assert "poufne" not in ticket.body
    assert "zainstalujemy nową wersję aplikacji" in ticket.body
    assert ticket.body_role == VENDOR_ROLE


def test_comments_keep_their_order_type_and_time() -> None:
    """Sprawdza, czy po normalizerze komentarze stoją w tej samej kolejności, z tym samym
    typem i czasem, a zmieniają się tylko treść i rola.

    Wyłapuje normalizer, który gubi albo przestawia komentarze: wątek czyta się jak
    chronologię, a najcenniejsze zdanie bywa w ostatnim komentarzu."""
    comments = [("klient", "Sprawdzamy."), ("konsultant", "Działa.")]
    raw      = mail_ticket("Nie działa wysyłka.", comments)
    ticket   = normalize_mail_ticket(raw, safe_templates(), safe_vendor_names())

    assert [(c.kind, c.created_at) for c in ticket.comments] == [
        (c.kind, c.created_at) for c in raw.comments
    ]
    assert [(c.role, c.body) for c in ticket.comments] == [
        (CLIENT_ROLE, "Sprawdzamy."),
        (VENDOR_ROLE, "Działa."),
    ]


def test_a_ticket_from_another_channel_comes_back_unchanged() -> None:
    """Sprawdza, czy zgłoszenie spoza kanału „Automat mailowy”, nawet ze stopką ze słownika
    szablonów i z powtórzeniem, wraca bez zmian, bez autora opisu.

    Wyłapuje czyszczenie wszystkich zgłoszeń: wątki spoza kanału parsowano bez niego, więc ich
    tekst dla modelu i dla indeksu rozjechałby się z kartami korpusu."""
    mail = safe_mail_ticket(41102)
    raw  = mail_ticket(mail.body, [("klient", mail.body)], category="Błąd")

    assert normalize_mail_ticket(raw, safe_templates(), safe_vendor_names()) == raw


def test_the_normalizer_cleans_a_mail_ticket_with_the_dictionary_from_its_directory() -> None:
    """Sprawdza, czy `MailNormalizer` na katalogu słownika zmyślonego oddaje zgłoszenie mailowe
    dokładnie takie, jak `normalize_mail_ticket()` ze słownikiem i nazwami z tego katalogu.

    Wyłapuje normalizer, który czyta inny plik albo pomija któryś krok: trasy i import
    czyściłyby inaczej, niż mierzy test ewaluacyjny."""
    raw = safe_mail_ticket(41101)

    assert MailNormalizer(SAFE_MAIL_DIR).normalize(raw) == normalize_mail_ticket(
        raw, safe_templates(), safe_vendor_names()
    )


def test_a_ticket_from_another_channel_needs_no_dictionary(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie spoza kanału „Automat mailowy” przechodzi przez normalizer bez
    zmian także wtedy, gdy katalogu słownika nie ma.

    Wyłapuje normalizer, który czyta słownik przy każdym zgłoszeniu: instancja bez słownika
    maili przestałaby obsługiwać wszystkie pozostałe kanały."""
    raw = mail_ticket("Nie działa wysyłka.", category="Błąd")

    assert MailNormalizer(tmp_path / "brak").normalize(raw) is raw


def test_a_mail_ticket_without_the_dictionary_is_a_configuration_error(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie z kanału „Automat mailowy” przy braku słownika maili kończy się
    błędem konfiguracji.

    Wyłapuje normalizer, który bez słownika przepuszcza wątek nieoczyszczony: anonimizator
    dostałby kilka razy dłuższy tekst z nazwiskami ze stopek, a nikt by tego nie zauważył."""
    with pytest.raises(MailDictionaryConfigError):
        MailNormalizer(tmp_path / "brak").normalize(safe_mail_ticket(41101))
