"""
Description:
Spójność zestawu scenariuszy trasy zamknięcia (`data/safe/golden/closed.json`) bez modelu: czy
każda sprawa jest żądaniem, które trasa przyjmie, i czy zestaw sprawdza każdy wynik. Test na
żywym modelu z wadliwym zestawem zapłaciłby za sprawy, które kończą się 422, albo mierzyłby
jeden wynik zamiast trzech, więc te warunki pilnuje się w domyślnym `pytest`.

| warunek                                       | czym grozi jego brak                        |
|-----------------------------------------------|---------------------------------------------|
| identyfikatory i numery zgłoszeń bez powtórek | dwie sprawy w jednym korpusie testu         |
|                                               | nadpisują sobie pliki                       |
| znany wynik przy każdej sprawie               | sprawa, której ocena nic nie znaczy         |
| każdy wynik ma co najmniej dwie sprawy        | wynik mierzony na jednym przypadku          |
| żądanie przechodzi walidację `TicketRequest`  | 422 w środku płatnego przebiegu             |
"""

from app.entry_routers.models import TicketRequest
from tests._helpers.scenarios.closed import EXPECTED_OUTCOMES, closed_cases

# Sprawy zestawu, czytane przy imporcie.
CASES = closed_cases()


def test_case_ids_and_ticket_numbers_are_unique() -> None:
    """Sprawdza, czy identyfikatory spraw i numery zgłoszeń w zestawie się nie powtarzają.

    Wyłapuje dwie sprawy o jednym numerze zgłoszenia: w jednym korpusie testu druga
    nadpisałaby pliki pierwszej, a raport mieszałby ich wyniki."""
    ids     = [case.case_id for case in CASES]
    tickets = [case.request["ticket_id"] for case in CASES]

    assert len(ids)     == len(set(ids))
    assert len(tickets) == len(set(tickets))


def test_every_case_expects_a_known_outcome() -> None:
    """Sprawdza, czy każda sprawa wymaga jednego z trzech wyników trasy: `blocked`, `indexed`
    albo `dropped`.

    Wyłapuje wynik z literówką: ocena nie uznałaby go ani za błąd bramki, ani filtra, więc
    sprawa przechodziłaby zawsze."""
    assert all(case.expected in EXPECTED_OUTCOMES for case in CASES)


def test_every_outcome_has_at_least_two_cases() -> None:
    """Sprawdza, czy każdy z trzech wyników ma w zestawie co najmniej dwie sprawy.

    Wyłapuje zestaw, który sprawdza bramkę albo filtr tylko w jedną stronę albo na jednym
    przypadku: błąd w drugą stronę przeszedłby bez czerwonego testu."""
    for outcome in EXPECTED_OUTCOMES:
        assert sum(case.expected == outcome for case in CASES) >= 2, outcome


def test_every_request_is_accepted_by_the_route() -> None:
    """Sprawdza, czy treść żądania każdej sprawy przechodzi walidację `TicketRequest`, czyli
    modelu wejścia trasy.

    Wyłapuje sprawę, na którą trasa odpowie 422, zanim zawoła model: test na żywym modelu
    liczyłby ją jako błąd trasy, choć zepsuty jest zestaw."""
    for case in CASES:
        TicketRequest.model_validate(case.request)
