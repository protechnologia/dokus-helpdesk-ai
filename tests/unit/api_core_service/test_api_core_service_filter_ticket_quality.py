from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_service.filter_ticket_quality import (
    MIN_RECORDS_FOR_DROP_RATE,
    drop_rate_warning,
    evaluate_ticket,
    filter_tickets,
)
from app.core_service.filter_ticket_quality_rules import RULES

# A record carrying real content, varied per test. Same starting point as the ParsedTicket tests, so
# a schema change breaks both files the same way instead of leaving this one testing a dead shape.
VALID_TICKET = {
    "ticket_id":                     "33644",
    "date":                          "2026-03-14",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka przez ePUAP kończy się błędem komunikacji",
    "symptoms":                      "Po kliknięciu Wyślij pojawia się komunikat o braku sieci",
    "error_codes":                   ["ERR-4210"],
    "cause":                         "Certyfikat bez uprawnienia AddDocumentToSign",
    "solution":                      "Wygenerowano certyfikat z właściwym uprawnieniem.",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "pytano o wersję przeglądarki",
    "excluded_causes":               [],
    "useful":                        True,
    "useful_reason":                 "Wątek podaje przyczynę i rozwiązanie.",
}


def _ticket(**overrides: object) -> ParsedTicket:
    """
    Description:
    Builds a record from the valid baseline with per-test overrides.

    Example args:
        solution="Brak rozstrzygnięcia w wątku."

    Example result:
        ParsedTicket(ticket_id="33644", solution="Brak rozstrzygnięcia w wątku.", …)
    """
    return ParsedTicket(**{**VALID_TICKET, **overrides})


# --- what the rule drops ------------------------------------------------------------------

def test_card_judged_not_useful_is_dropped() -> None:
    """Sprawdza, czy karta, którą model ocenił jako nieprzydatną (`useful` = false), jest
    odrzucana regułą `not_useful`, a dowodem w werdykcie jest uzasadnienie modelu, słowo w słowo.

    Wyłapuje dwie usterki: kartę bez wiedzy przepuszczoną do indeksu, gdzie przy wyszukiwaniu
    wygląda na odpowiedź, oraz odrzucenie bez uzasadnienia, po którym nie da się sprawdzić, czy
    model miał rację."""
    reason  = "Wątek potwierdza jedynie usunięcie sprawy na prośbę."
    ticket  = _ticket(solution="Usunięto sprawę.", useful=False, useful_reason=reason)
    verdict = evaluate_ticket(ticket)

    assert not verdict.keep
    assert verdict.reasons == ["not_useful"]
    assert verdict.hits[0].evidence == reason


# --- what the rule must NOT drop ----------------------------------------------------------

def test_useful_card_without_solution_is_kept() -> None:
    """Sprawdza, czy karta z „brak” w rozwiązaniu, ale z ustaloną przyczyną i oceną „przydatna”,
    zostaje w indeksie.

    Wyłapuje powrót do filtrowania po słowie „brak” w `solution`: wypadłyby wtedy karty, w których
    wątek ustalił przyczynę, a naprawy nie opisał — przyczyna to wiedza, której agent potrzebuje
    przy tym samym objawie."""
    ticket = _ticket(
        solution      = "brak",
        cause         = "Stanowisko miało minioną datę ważności.",
        useful        = True,
        useful_reason = "Przyczyna przeniesie się na inne instalacje.",
    )

    assert evaluate_ticket(ticket).keep


def test_ordinary_solution_is_kept() -> None:
    """Sprawdza, czy zwykłe zgłoszenie, z rozwiązaniem opisującym wykonaną pracę, zostaje i nie
    uruchamia żadnej reguły: werdykt jest pozytywny, a lista trafień reguł pusta.

    Wyłapuje fałszywy alarm na poprawnym zgłoszeniu: filtr wycinałby wtedy z indeksu zgłoszenia,
    które niosą wiedzę."""
    verdict = evaluate_ticket(_ticket())

    assert verdict.keep
    assert verdict.hits == []


# --- report -------------------------------------------------------------------------------

def test_report_splits_kept_from_dropped() -> None:
    """Sprawdza, czy raport dzieli zgłoszenia na zachowane i odrzucone: z trzech zgłoszeń, z których
    drugie model ocenił jako nieprzydatne, zachowane są pierwsze i trzecie, a odrzucone drugie.

    Wyłapuje zgłoszenie po złej stronie podziału albo zgubione w raporcie: indeksacja bierze
    z raportu listę zachowanych, więc puste zgłoszenie weszłoby do indeksu albo dobre by z niego
    wypadło."""
    report = filter_tickets(
        [
            _ticket(ticket_id="1"),
            _ticket(ticket_id="2", useful=False),
            _ticket(ticket_id="3"),
        ]
    )

    assert [v.ticket_id for v in report.kept]    == ["1", "3"]
    assert [v.ticket_id for v in report.dropped] == ["2"]


def test_report_counts_drops_per_reason() -> None:
    """Sprawdza, czy raport liczy odrzucenia osobno dla każdej reguły: przy dwóch zgłoszeniach,
    z których jedno model ocenił jako nieprzydatne, wynik to jedno odrzucenie regułą `not_useful`.

    Wyłapuje raport, który podaje tylko łączną liczbę odrzuconych albo liczy je źle: w jednej sumie
    nie widać reguły, która odrzuca nie te zgłoszenia, co trzeba."""
    report = filter_tickets([_ticket(ticket_id="1", useful=False), _ticket(ticket_id="2")])

    assert report.by_reason() == {"not_useful": 1}


def test_report_lists_ticket_ids_per_rule() -> None:
    """Sprawdza, czy raport podaje numery zgłoszeń odrzuconych przez daną regułę: przy dwóch
    zgłoszeniach, z których odrzucone jest 19596, lista dla reguły `not_useful` zawiera tylko ten
    numer.

    Wyłapuje raport, który zna samą liczbę odrzuceń: bez numerów nie da się zajrzeć do odrzuconych
    zgłoszeń i sprawdzić, czy reguła miała rację."""
    report = filter_tickets([_ticket(ticket_id="19596", useful=False), _ticket(ticket_id="2")])

    assert report.ticket_ids_for("not_useful") == ["19596"]


def test_empty_corpus_is_an_empty_report() -> None:
    """Sprawdza, czy pusta lista zgłoszeń daje pusty raport, bez werdyktów i bez odrzuceń, a nie
    wyjątek.

    Wyłapuje filtr, który wywraca się, gdy nie ma czego oceniać: korpus, którego jeszcze nie
    zbudowano, to zwykły stan, a nie błąd."""
    report = filter_tickets([])

    assert report.verdicts == []
    assert report.by_reason() == {}


# --- drop-rate warning: the guard against the rules going silent ---------------------------

def test_silent_filter_is_reported() -> None:
    """Sprawdza, czy filtr ostrzega, gdy z dużej paczki zgłoszeń nie odrzucił żadnego: paczka ma
    tyle zgłoszeń, ile wynosi próg `MIN_RECORDS_FOR_DROP_RATE`, a ostrzeżenie każe sprawdzić reguły.

    Wyłapuje zniknięcie tego ostrzeżenia. Reguła czyta ocenę wydaną przez model, więc po zmianie
    promptu albo modelu może przestać odrzucać cokolwiek i sama tego nie zauważy: każde
    zgłoszenie przechodzi, a żaden błąd się nie pojawia."""
    report = filter_tickets([_ticket(ticket_id=str(i)) for i in range(MIN_RECORDS_FOR_DROP_RATE)])

    assert "reguły" in (drop_rate_warning(report) or "")


def test_plausible_drop_rate_is_silent() -> None:
    """Sprawdza, czy filtr nie ostrzega, gdy odrzuca mniej więcej tyle, ile przewidują pomiary:
    w paczce o wielkości progu `MIN_RECORDS_FOR_DROP_RATE` model ocenił jako nieprzydatną co
    trzecią kartę.

    Wyłapuje ostrzeżenie przy zdrowym przebiegu: alarm, który odzywa się zawsze, przestaje być
    czytany i nie pomoże wtedy, gdy reguły naprawdę zamilkną."""
    tickets = [_ticket(ticket_id=str(i)) for i in range(MIN_RECORDS_FOR_DROP_RATE)]
    # Mniej więcej zmierzone 30%, z zapasem w granicach tolerancji.
    for i in range(MIN_RECORDS_FOR_DROP_RATE // 3):
        tickets[i] = _ticket(ticket_id=str(i), useful=False)

    assert drop_rate_warning(filter_tickets(tickets)) is None


def test_small_batch_never_warns() -> None:
    """Sprawdza, czy przy garstce zgłoszeń filtr nie ostrzega, choć nic nie odrzucił: tu paczka to
    jedno poprawne zgłoszenie.

    Wyłapuje ostrzeżenie liczone na zbyt małej paczce: przy kilku zgłoszeniach odsetek odrzuceń nic
    nie znaczy, a przy sprawdzaniu jednego zgłoszenia zero odrzuconych to wynik poprawny."""
    report = filter_tickets([_ticket()])

    assert drop_rate_warning(report) is None


# --- the rule registry --------------------------------------------------------------------

def test_every_rule_is_reachable_by_name() -> None:
    """Sprawdza, czy każda reguła z rejestru `RULES` ma własną nazwę funkcji i docstring. Test
    przechodzi po całym rejestrze, więc nowa reguła jest sprawdzana bez zmian w teście.

    Wyłapuje regułę bez nazwy albo bez opisu: raport grupuje odrzucenia po nazwie reguły, więc
    reguły, której nie da się nazwać, nie dałoby się policzyć."""
    for rule in RULES:
        assert rule.__name__
        assert rule.__doc__, f"{rule.__name__} bez docstringa"
