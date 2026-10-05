from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_service.builder_ticket_embedding_text import build_embedding_text

PROBLEM  = "Wysyłka przez ePUAP kończy się błędem komunikacji"
SYMPTOMS = "Po kliknięciu Wyślij pojawia się komunikat o braku sieci"


def test_problem_and_symptoms_go_on_separate_lines() -> None:
    """Sprawdza, czy z opisu problemu i z objawów powstaje jeden tekst: problem w pierwszej linii,
    objawy w drugiej.

    Wyłapuje zmianę tego układu, na przykład inną kolejność albo inny znak między polami: z tego
    tekstu embedder liczy wektor zgłoszenia, więc po zmianie nowe wektory przestałyby pasować do
    tych, które są już w indeksie."""
    assert build_embedding_text(problem=PROBLEM, symptoms=SYMPTOMS) == f"{PROBLEM}\n{SYMPTOMS}"


def test_the_record_side_builds_the_same_text() -> None:
    """Sprawdza, czy sparsowane zgłoszenie (`ParsedTicket.embedding_text()`) składa dokładnie ten
    sam tekst co funkcja `build_embedding_text()` wywołana z tym samym problemem i objawami.

    Wyłapuje rozjazd między indeksacją a zapytaniem: zgłoszenia w indeksie powstają pierwszą drogą,
    zapytania drugą, a gdyby teksty się różniły, wektory przestałyby być porównywalne i żaden błąd
    by tego nie pokazał."""
    ticket = ParsedTicket(
        ticket_id                     = "33644",
        date                          = "2026-03-14",
        component                     = "ePUAP",
        problem                       = PROBLEM,
        symptoms                      = SYMPTOMS,
        cause                         = "Certyfikat bez uprawnienia AddDocumentToSign",
        solution                      = "Wygenerowano certyfikat z właściwym uprawnieniem.",
        resolution                    = "naprawione",
        resolution_vocabulary_version = 1,
    )

    assert ticket.embedding_text() == build_embedding_text(problem=PROBLEM, symptoms=SYMPTOMS)
