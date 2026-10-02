from app.model.filter_quality_report import QualityReport
from app.model.filter_quality_verdict import QualityVerdict, RuleHit
from app.model.ticket_parsed import ParsedTicket
from app.service.filter_ticket_quality_rules import RULES

# Udział korpusu, który filtr powinien odrzucić. Zmierzony dwa razy na różnych próbkach: 19%
# zestawu odniesienia z 200 rekordów, 25–26% na 661 rekordach przejrzanych wcześniej. Wynik daleko
# poniżej znaczy, że reguły rozminęły się z tym, co pisze parser, a nie, że korpus się poprawił.
EXPECTED_DROP_RATE = 0.19

# O ile odsetek odrzuceń może spaść, zanim przebieg to zgłosi. Szeroko celowo — chodzi o złapanie
# filtra, który ZAMILKŁ (zmieniony prompt, podmieniony model), a nie o pilnowanie zwykłych wahań.
DROP_RATE_TOLERANCE = 0.5

# Poniżej tylu rekordów odsetek odrzuceń nic nie mówi: przy garstce zgłoszeń jedna decyzja przesuwa
# go o dziesiątki punktów procentowych. Bez tego progu sprawdzian odpalałby przy każdej zdrowej
# małej paczce — także przy wywołaniu runtime na jednym zgłoszeniu, gdzie 0% odrzuconych to wynik
# POPRAWNY.
MIN_RECORDS_FOR_DROP_RATE = 50


def evaluate_ticket(
    ticket: ParsedTicket,  # np. ParsedTicket(ticket_id="19596", …)
) -> QualityVerdict:
    """
    Description:
    Ocenia JEDEN rekord i zwraca werdykt z zebranymi dowodami. To punkt wejścia dla obu
    wołających: wsadowego przebiegu indeksacji z etapu 4 i sprawdzenia w runtime pojedynczego
    zamkniętego zgłoszenia. `filter_tickets()` niżej to ta sama funkcja na korpusie plus
    statystyki potrzebne przebiegowi wsadowemu — nic więcej.

    Działają wszystkie reguły, żadna nie przerywa przebiegu: rekord bywa pusty z więcej niż
    jednego powodu, a raport grupuje odrzucenia per reguła, więc zatrzymanie na pierwszym
    trafieniu zaniżałoby wynik tej reguły, która akurat stoi dalej w krotce.

    Nie mylić z BRAMKĄ ZAMKNIĘCIA (graf `gate_close`). Obie patrzą na tę samą oś — czy jest
    problem i rozstrzygnięcie — ale odpowiadają na inne pytania („czy warto to trzymać w indeksie"
    wobec „czy wolno to zamknąć"), zwracają inne kształty, a bramka woła LLM. To kandydat na tani
    pre-filtr przed tą bramką, nigdy jej zamiennik.

    Example args:
        ticket=ParsedTicket(ticket_id="19596", solution="Brak rozstrzygnięcia w wątku.", …)

    Example result:
        QualityVerdict(ticket_id="19596", hits=[RuleHit(rule="no_resolution", evidence="Brak…")])
    """
    hits = []

    for rule in RULES:
        evidence = rule(ticket.solution)

        if evidence is not None:
            hits.append(RuleHit(rule=rule.__name__, evidence=evidence))

    return QualityVerdict(ticket_id=ticket.ticket_id, hits=hits)


def filter_tickets(
    tickets: list[ParsedTicket],  # np. [ParsedTicket(ticket_id="33644", …)]
) -> QualityReport:
    """
    Description:
    Ocenia cały korpus i zwraca raport, który drukuje przebieg indeksacji.

    Przyjmuje rekordy, a nie katalog: czytanie i walidacja artefaktów należą do
    `validator_ticket_parsed`, a filtra, który sam chodziłby po dysku, nie dałoby się zmierzyć na
    ręcznie zbudowanej liście przypadków brzegowych.

    Example args:
        tickets=[ParsedTicket(ticket_id="33644", …), ParsedTicket(ticket_id="19596", …)]

    Example result:
        QualityReport(verdicts=[QualityVerdict(ticket_id="33644", hits=[]), …])
    """
    return QualityReport(verdicts=[evaluate_ticket(ticket) for ticket in tickets])


def drop_rate_warning(
    report: QualityReport,  # np. QualityReport(verdicts=[…])
) -> str | None:
    """
    Description:
    Zwraca ostrzeżenie, gdy filtr odrzucił znacznie mniej korpusu, niż każą oczekiwać wszystkie
    pomiary, albo None, gdy odsetek jest wiarygodny lub paczka jest za mała, by go ocenić.

    Po co to jest: reguły czytają tekst napisany przez model językowy, więc psują się przez
    ZAMILKNIĘCIE — zmieniony prompt parsujący albo podmieniony model i nagle nic nie pasuje, każdy
    rekord przechodzi, a indeks zapełnia się pustymi wpisami, choć nic nie świeci na czerwono.
    Liczba odrzuconych to jedyny sygnał, który nie może zawieść tak jak reguły, bo nie zależy od
    żadnego sformułowania.

    Celowo ostrzeżenie, nie wyjątek: naprawdę lepszy korpus też by je wyzwolił, a przerwanie
    przebiegu indeksacji z powodu statystyki byłoby błędem.

    Example args:
        report=QualityReport(verdicts=[…])  # 200 rekordów, 4 odrzucone

    Example result:
        "filtr odrzucił 2.0% korpusu, oczekiwane ~19% — sprawdź, czy reguły nadal pasują do
         artefaktów (zmiana promptu parsującego albo modelu?)"
    """
    # Za mało rekordów, by odsetek coś znaczył — także przy wywołaniu runtime na jednym zgłoszeniu.
    if len(report.verdicts) < MIN_RECORDS_FOR_DROP_RATE:
        return None

    rate = len(report.dropped) / len(report.verdicts)

    if rate >= EXPECTED_DROP_RATE * DROP_RATE_TOLERANCE:
        return None

    return (
        f"filtr odrzucił {rate:.1%} korpusu, oczekiwane ~{EXPECTED_DROP_RATE:.0%} — sprawdź, "
        f"czy reguły nadal pasują do artefaktów (zmiana promptu parsującego albo modelu?)"
    )
