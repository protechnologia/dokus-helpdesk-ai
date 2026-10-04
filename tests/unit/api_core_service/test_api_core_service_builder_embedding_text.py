from app.core_model.ticket_parsed import ParsedTicket
from app.core_service.builder_embedding_text import build_embedding_text

PROBLEM  = "Wysyłka przez ePUAP kończy się błędem komunikacji"
SYMPTOMS = "Po kliknięciu Wyślij pojawia się komunikat o braku sieci"


def test_problem_and_symptoms_go_on_separate_lines() -> None:
    """Dwa pola → jeden tekst, `problem` nad `symptoms`: to z niego embedder liczy wektor."""
    assert build_embedding_text(problem=PROBLEM, symptoms=SYMPTOMS) == f"{PROBLEM}\n{SYMPTOMS}"


def test_the_record_side_builds_the_same_text() -> None:
    """Rekord o tych samych polach → ten sam tekst co funkcja: indeksacja i zapytanie nie mogą
    się rozjechać, bo wektory przestałyby być porównywalne bez żadnego błędu."""
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
