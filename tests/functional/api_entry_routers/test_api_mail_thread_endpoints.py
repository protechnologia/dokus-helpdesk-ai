"""
Description:
Wątki kanału „Automat mailowy” w trasach grafów (p. 32.4): `/search`, `/gate/close`,
`/parse-ticket` i `/suggest` podają grafowi wątek oczyszczony normalizerem maili, a zgłoszenie
z innego kanału bez zmian. Pierwszy krok każdego grafu to anonimizacja, więc test patrzy na
tekst, który dostaje anonimizator. Słownik maili jest zmyślony, z `data/safe/mail/`.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core_service.loader_mail_dictionary import MailDictionaryConfigError
from app.core_service.normalizer_ticket_mail import MailNormalizer
from app.engine_anonymization import FakeAnonymizer
from tests._helpers.mail import SAFE_MAIL_DIR, safe_mail_request
from tests._helpers.mail.samples import sample_cleaned_thread
from tests._helpers.routers import app_on_fake_graphs, ticket_request
from tests._helpers.routers.samples import GRAPH_REQUESTS

# Trasy grafów, które przyjmują zgłoszenie z wątkiem; `/gate/reply` i `/polish` biorą samą
# wiadomość albo notatki, więc kanału zgłoszenia nie znają.
TICKET_ROUTES = ["/search", "/gate/close", "/parse-ticket", "/suggest"]


@pytest.mark.parametrize("route", TICKET_ROUTES)
def test_a_mail_thread_reaches_the_graph_cleaned(route: str) -> None:
    """Sprawdza, czy zgłoszenie z kanału „Automat mailowy” dociera do grafu (do anonimizatora,
    jego pierwszego kroku) jako wątek oczyszczony: bez drugiej kopii maila, stopki i cytatu,
    z autorami z podpisów — znak w znak taki jak wątek wzorcowy normalizera.

    Wyłapuje trasę, która podaje grafowi surowy mail: anonimizator dostałby kilka razy dłuższy
    tekst z nazwiskami ze stopek i cytatów, a model — odpowiedzi konsultanta jako słowa klienta."""
    anonymizer = FakeAnonymizer()
    app        = app_on_fake_graphs(anonymizer, MailNormalizer(SAFE_MAIL_DIR))

    TestClient(app).post(route, json=ticket_request(route, safe_mail_request(41101)))

    assert anonymizer.texts == [sample_cleaned_thread()]


@pytest.mark.parametrize("route", TICKET_ROUTES)
def test_a_ticket_from_another_channel_needs_no_mail_dictionary(route: str, tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie spoza kanału „Automat mailowy” przechodzi przez trasę i trafia
    do grafu bez zmian także wtedy, gdy słownika maili nie ma.

    Wyłapuje trasę, która czyta słownik przy każdym zgłoszeniu: instancja bez słownika maili
    przestałaby obsługiwać wszystkie pozostałe kanały."""
    anonymizer = FakeAnonymizer()
    app        = app_on_fake_graphs(anonymizer, MailNormalizer(tmp_path / "brak"))

    response = TestClient(app).post(route, json=GRAPH_REQUESTS[route])

    assert response.status_code == 200
    assert anonymizer.texts[0].startswith("ZGŁOSZENIE 41002")
    assert "OPIS ZGŁASZAJĄCEGO:\nOd wczoraj nie przychodzą przesyłki" in anonymizer.texts[0]


@pytest.mark.parametrize("route", TICKET_ROUTES)
def test_a_mail_ticket_without_the_dictionary_fails_loudly(route: str, tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie z kanału „Automat mailowy” przy braku słownika maili kończy się
    błędem konfiguracji, zanim cokolwiek trafi do anonimizatora.

    Wyłapuje trasę, która przy braku słownika podaje grafowi surowy mail albo zamienia błąd
    konfiguracji na 503: helpdesk ponawiałby żądanie, a czekanie niczego nie naprawi."""
    anonymizer = FakeAnonymizer()
    app        = app_on_fake_graphs(anonymizer, MailNormalizer(tmp_path / "brak"))

    with pytest.raises(MailDictionaryConfigError):
        TestClient(app).post(route, json=ticket_request(route, safe_mail_request(41101)))

    assert anonymizer.texts == []
