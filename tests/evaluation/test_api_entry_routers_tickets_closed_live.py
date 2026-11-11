"""
Description:
Scenariusze ewaluacyjne trasy `POST /tickets/closed` na żywym modelu (p. 30): czy zamknięte
zgłoszenie kończy się wynikiem, którego wymaga — zablokowane przez bramkę zamknięcia, w indeksach
albo odrzucone przez filtr jakości. Trasa chodzi naprawdę, z bramką i kartą na modelu
generującym; atrapami są anonimizator, embedder i obie bazy, a pliki korpusu idą do katalogu
testu. Zestaw leży w `data/safe/golden/closed.json`: po dwie sprawy na każdy wynik.

| test                                    | co sprawdza                                       |
|-----------------------------------------|---------------------------------------------------|
| `test_every_close_gets_a_result`        | trasa oddaje wynik każdej sprawy                  |
| `test_no_good_close_is_blocked`         | bramka przepuszcza zamknięcie z problemem i pracą |
| `test_no_bare_close_reaches_the_corpus` | bramka zatrzymuje zamknięcie bez problemu albo    |
|                                         | bez tego, co zrobiono                             |
| `test_the_filter_decides_as_expected`   | filtr przyjmuje kartę z wiedzą i odrzuca kartę    |
|                                         | bez niej                                          |

Pomiary:

| zgodnych | błędy bramki | błędy filtra | błędy trasy | pomiar                                 |
|----------|--------------|--------------|-------------|----------------------------------------|
| 6 z 6    | 0            | 0            | 0           | 2026-11-11, `gpt-6.1-sol`, 2 przebiegi |

Uzasadnienia z pierwszego pomiaru: bramka blokuje „Zamykam.” i „Problem rozwiązany” jako brak
opisu działań, filtr odrzuca termin szkolenia i usunięcie duplikatu jako wiedzę jednorazową.

O czym pamiętać przy zmianach:

- Progu nie ma: każdy zły wynik to poprawka promptu bramki, promptu karty albo reguły, a sprawę
  poprawia się tylko wtedy, gdy błędna jest ona sama, nigdy pod wynik.
- Liczy się sam wynik. Dlaczego bramka zablokowała albo filtr odrzucił kartę, mówią uzasadnienie
  werdyktu i `useful_reason` w raporcie, który pytest wypisuje po przebiegu; czyta się je przy
  pierwszym pomiarze i przy każdej zmianie wyniku.
- To, co robi serwis korpusu (pliki, indeksy, ponowne zamknięcie), sprawdzają testy funkcjonalne
  trasy bez modelu; tutaj liczy się decyzja modelu.
- KOSZTUJE: sprawa to jedna tura bramki, a po przepuszczeniu jedna tura karty; sześć spraw na
  `gpt-6.1-sol` to kilka centów i kilkanaście sekund.
"""


import pytest

from tests._helpers.live import LiveUsageReport, live_generation_llm
from tests._helpers.scenarios.closed import ClosedOutcome, ClosedReport, measure_closed_cases

pytestmark = pytest.mark.llm_live


@pytest.fixture(scope="module")
def outcomes(
    request:          pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór z `-m`
    tmp_path_factory: pytest.TempPathFactory,  # wstrzykiwane przez pytest; katalog korpusu
    live_usage:       LiveUsageReport,         # wstrzykiwane przez pytest; raport zużycia
    closed_report:    ClosedReport,            # wstrzykiwane przez pytest; raport ocen spraw
) -> list[ClosedOutcome]:
    """
    Description:
    Przeprowadza wszystkie sprawy zestawu przez trasę na żywym modelu, raz na cały plik, i oddaje
    ich oceny.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        [ClosedOutcome(case=ClosedCase(case_id="c01", …), status=200, answer="indexed", …), …]
    """
    llm  = live_generation_llm(request.config)
    root = tmp_path_factory.mktemp("korpus")

    return measure_closed_cases(llm, root, live_usage, closed_report)


def test_every_close_gets_a_result(outcomes: list[ClosedOutcome]) -> None:
    """Sprawdza, czy trasa oddaje wynik (kod 200) na każde zamknięcie z zestawu.

    Wyłapuje prompt bramki albo karty, przy którym model nie oddaje odpowiedzi w kształcie
    narzędzia nawet po poprawce, i błąd w kodzie trasy: helpdesk dostawałby 503 albo 500
    i zgłoszenie nie trafiałoby do korpusu."""
    failed = [outcome for outcome in outcomes if outcome.failed]

    assert not failed, "bez wyniku — " + ", ".join(
        f"{outcome.case.label} (kod {outcome.status})" for outcome in failed
    )


def test_no_good_close_is_blocked(outcomes: list[ClosedOutcome]) -> None:
    """Sprawdza, czy bramka nie blokuje żadnego zamknięcia, z którego wynika problem i to, co
    zrobiono — także takiego, którego karta potem odpada w filtrze.

    Wyłapuje bramkę, która zatrzymuje dobre zamknięcia: wiedza z nich nie trafiałaby do
    korpusu, a wdrożeniowcy uczyliby się obchodzić bramkę bez czytania."""
    blocked = [outcome for outcome in outcomes if outcome.false_block]

    assert not blocked, "zablokowane bez powodu — " + ", ".join(
        outcome.case.label for outcome in blocked
    )


def test_no_bare_close_reaches_the_corpus(outcomes: list[ClosedOutcome]) -> None:
    """Sprawdza, czy bramka zatrzymuje każde zamknięcie, z którego nie wynika problem albo to, co
    zrobiono, tak że karta nie powstaje.

    Wyłapuje bramkę, która przepuszcza „Zamykam.” i „Problem rozwiązany.”: do korpusu szłyby
    karty bez wiedzy, a każda kosztowałaby drugi przebieg modelu."""
    passed = [outcome for outcome in outcomes if outcome.missed_block]

    assert not passed, "przepuszczone przez bramkę — " + ", ".join(
        outcome.case.label for outcome in passed
    )


def test_the_filter_decides_as_expected(outcomes: list[ClosedOutcome]) -> None:
    """Sprawdza, czy po przepuszczeniu przez bramkę karta z wiedzą trafia do indeksów, a karta
    z wiedzą tylko o tej sprawie (termin, wykonana prośba) jest odrzucana przez filtr.

    Wyłapuje kartę, którą model ocenia odwrotnie: wiedza z dobrego zamknięcia nie trafiałaby do
    wyszukiwania albo wyszukiwanie podsuwałoby wdrożeniowcom sprawy bez treści."""
    wrong = [outcome for outcome in outcomes if outcome.wrong_filter]

    assert not wrong, "filtr zdecydował inaczej — " + ", ".join(
        f"{outcome.case.label}: {outcome.answer}" for outcome in wrong
    )
