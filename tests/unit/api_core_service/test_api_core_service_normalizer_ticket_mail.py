"""
Description:
Reguła autora wiadomości z `core_service/normalizer_ticket_mail.py` i treść wiadomości, którą
widzi normalizer: w kanale „Automat mailowy” role z bazy są błędne, więc autora mówi podpis
firmy dostawcy we własnej części wiadomości (p. 32). Testy całego normalizera, na słowniku
zmyślonym z `data/safe/mail/`, leżą w `tests/integration/`.
"""

from app.core_model.dicts.vendor_names import VendorNames
from app.core_service.normalizer_ticket_mail import (
    CLIENT_ROLE,
    VENDOR_ROLE,
    message_author,
    message_texts,
)
from tests._helpers.mail import VENDOR_NAME, mail_ticket
from tests._helpers.mail.samples import (
    sample_client_reply_quoting_vendor,
    sample_forward,
    sample_mail_with_own_header,
    sample_vendor_reply,
)

# Nazwy dostawcy jak w słowniku zmyślonym.
VENDORS = VendorNames(names=[VENDOR_NAME])


def test_a_vendor_signature_in_the_own_part_makes_the_vendor_the_author() -> None:
    """Sprawdza, czy wiadomość z nazwą dostawcy w podpisie nad cytatem ma autora
    `konsultant`, choć baza zapisała ją jako wiadomość klienta.

    Wyłapuje zaufanie roli z bazy: w tym kanale odpowiedzi dostawcy figurują jako wypowiedzi
    klienta, więc model brałby rozwiązanie dostawcy za relację klienta."""
    assert message_author(sample_vendor_reply(), CLIENT_ROLE, VENDORS) == VENDOR_ROLE


def test_a_vendor_signature_only_in_the_quote_leaves_the_client() -> None:
    """Sprawdza, czy odpowiedź klienta, pod którą stoi cytat odpowiedzi dostawcy z jego
    podpisem, ma autora `klient`.

    Wyłapuje szukanie nazwy dostawcy w całej wiadomości: każda odpowiedź klienta na mail
    dostawcy cytuje jego podpis, więc każda stałaby się wiadomością dostawcy."""
    assert message_author(sample_client_reply_quoting_vendor(), CLIENT_ROLE, VENDORS) == CLIENT_ROLE


def test_the_consultant_role_from_the_source_stays() -> None:
    """Sprawdza, czy wiadomość zapisana w źródle jako wiadomość konsultanta ma autora
    `konsultant` także bez podpisu z nazwą dostawcy.

    Wyłapuje regułę, która nadpisuje jedyną pewną rolę z bazy: system zapisuje konsultanta
    tylko przy odpowiedzi z helpdesku, a krótka odpowiedź podpisu nie ma."""
    assert message_author("Proszę ponowić wysyłkę.", VENDOR_ROLE, VENDORS) == VENDOR_ROLE


def test_the_brand_without_its_legal_form_is_not_a_signature() -> None:
    """Sprawdza, czy wiadomość, w której klient pisze o firmie dostawcy samą marką, bez formy
    prawnej, ma autora `klient`.

    Wyłapuje porównanie po samym pierwszym słowie nazwy: klient, który pisze „do firmy
    Przykładsoft”, stałby się dostawcą."""
    text = "Piszę do firmy Przykładsoft w sprawie wysyłki pism.\nJan Kowalski"

    assert message_author(text, CLIENT_ROLE, VENDORS) == CLIENT_ROLE


def test_a_forward_without_own_text_takes_the_author_of_the_forwarded_mail() -> None:
    """Sprawdza, czy przekazanie z samym „FYI” nad wiadomością dostawcy z jego podpisem ma
    autora `konsultant`.

    Wyłapuje własną część kończoną na pierwszym nagłówku za jednym słowem: przekazania
    zapowiedzi dostawcy dostawałyby autora `klient` (na 136 wątkach kanału dwa takie pola)."""
    assert message_author(sample_forward(), CLIENT_ROLE, VENDORS) == VENDOR_ROLE


def test_the_header_at_the_start_of_the_field_belongs_to_the_message() -> None:
    """Sprawdza, czy wiadomość zapisana razem ze swoim nagłówkiem („Od:”, „Do:”, „Temat:” na
    początku pola) ma autora z podpisu pod treścią, także zapisanego wielkimi literami i bez
    odstępów („PRZYKŁADSOFT sp.z o.o.”).

    Wyłapuje własną część kończoną na nagłówku samej wiadomości (pusta część, autor zawsze
    `klient`) i porównanie nazwy znak w znak."""
    assert message_author(sample_mail_with_own_header(), CLIENT_ROLE, VENDORS) == VENDOR_ROLE


def test_message_texts_drop_image_references() -> None:
    """Sprawdza, czy treść wiadomości dla normalizera to opis i komentarze po kolei, bez
    odwołań do obrazków (`[cid:…]`) i bez odstępu przed nimi.

    Wyłapuje odwołania zostawione w treści: identyfikator obrazka jest inny w każdej kopii
    maila, więc linia z podpisem i logo nie zniknęłaby jako powtórzenie."""
    ticket = mail_ticket(
        "Pozdrawiam [cid:image001.png@01DCF2C1.5B3E9A40]\nJan Kowalski",
        [("klient", "[cid:image002.png@01DCF2C1.5B3E9A40]\nAnna Nowak")],
    )

    assert message_texts(ticket) == ["Pozdrawiam\nJan Kowalski", "\nAnna Nowak"]
