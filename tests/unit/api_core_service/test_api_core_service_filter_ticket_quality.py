import pytest

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

@pytest.mark.parametrize(
    "solution",
    [
        "brak",                                                     # the schema's own escape value
        "nie dotyczy",                                              # the other escape value
        "Brak rozstrzygnięcia w wątku.",                            # escape phrase plus filler
        "Brak rozstrzygnięcia - problem pozostaje nierozwiązany.",   # still nothing done
        "Rozwiązane do zamknięcia (brak szczegółów co do sposobu)",  # admission mid-sentence
    ],
)
def test_hollow_solution_is_dropped(solution: str) -> None:
    """Sprawdza, czy zgłoszenie, którego rozwiązanie tylko przyznaje, że rozwiązania nie ma, jest
    odrzucane regułą `no_resolution`, a werdykt niesie fragment tego tekstu jako dowód. Pięć
    przypadków: samo „brak", „nie dotyczy" i trzy zdania, które poza takim przyznaniem prawie nic
    nie dodają.

    Wyłapuje dwie usterki: puste zgłoszenie przepuszczone do indeksu, gdzie przy wyszukiwaniu
    wygląda na odpowiedź, oraz odrzucenie bez dowodu, po którym nie da się sprawdzić, czy reguła
    miała rację."""
    verdict = evaluate_ticket(_ticket(solution=solution))

    assert not verdict.keep
    assert verdict.reasons == ["no_resolution"]
    assert verdict.hits[0].evidence


# --- what the rule must NOT drop ----------------------------------------------------------

@pytest.mark.parametrize(
    "solution",
    [
        # A refusal is the most valuable class in this corpus — it says what NOT to attempt. It
        # opens with the same word as an empty record, so only the amount of text tells them apart.
        "Brak możliwości wygenerowania ZPO w tej sytuacji. Klient musi zaakceptować brak"
        " potwierdzenia, ponieważ operator nie wystawia go dla przesyłek nierejestrowanych.",
        # "No change in the system" plus an explanation: the client learns how it actually works.
        "Brak zmian w systemie. Klient otrzymał wyjaśnienie, jak działa mechanizm eksportu danych"
        " i dlaczego kolumny pojawiają się w tej kolejności.",
        # `brak` as a PREFIX of an ordinary adjective, in a record describing work that was done.
        # This one cost a false positive until the pattern moved to whole-word matching.
        "Dodano brakujące ustawienie systemowe. Wykonuje dostawca.",
        "Konsultant utworzył brakujące katalogi do końca roku i potwierdził, że błąd znika.",
    ],
)
def test_solution_with_content_is_kept(solution: str) -> None:
    """Sprawdza, czy zgłoszenie zostaje, gdy słowo „brak" otwiera prawdziwą treść albo jest tylko
    częścią innego słowa. Cztery przypadki: odmowa z uzasadnieniem, „brak zmian w systemie"
    z wyjaśnieniem dla klienta i dwa rozwiązania ze słowem „brakujące".

    Wyłapuje regułę, która odrzuca po samym słowie „brak": z indeksu wypadłyby odmowy, czyli
    najcenniejsze zgłoszenia, bo mówią, czego nie próbować, oraz opisy wykonanej pracy."""
    assert evaluate_ticket(_ticket(solution=solution)).keep


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
    drugie ma w rozwiązaniu samo „brak", zachowane są pierwsze i trzecie, a odrzucone drugie.

    Wyłapuje zgłoszenie po złej stronie podziału albo zgubione w raporcie: indeksacja bierze
    z raportu listę zachowanych, więc puste zgłoszenie weszłoby do indeksu albo dobre by z niego
    wypadło."""
    report = filter_tickets(
        [
            _ticket(ticket_id="1"),
            _ticket(ticket_id="2", solution="brak"),
            _ticket(ticket_id="3"),
        ]
    )

    assert [v.ticket_id for v in report.kept]    == ["1", "3"]
    assert [v.ticket_id for v in report.dropped] == ["2"]


def test_report_counts_drops_per_reason() -> None:
    """Sprawdza, czy raport liczy odrzucenia osobno dla każdej reguły: przy dwóch zgłoszeniach,
    z których jedno ma w rozwiązaniu samo „brak", wynik to jedno odrzucenie regułą `no_resolution`.

    Wyłapuje raport, który podaje tylko łączną liczbę odrzuconych albo liczy je źle: w jednej sumie
    nie widać reguły, która odrzuca nie te zgłoszenia, co trzeba."""
    report = filter_tickets([_ticket(ticket_id="1", solution="brak"), _ticket(ticket_id="2")])

    assert report.by_reason() == {"no_resolution": 1}


def test_report_lists_ticket_ids_per_rule() -> None:
    """Sprawdza, czy raport podaje numery zgłoszeń odrzuconych przez daną regułę: przy dwóch
    zgłoszeniach, z których odrzucone jest 19596, lista dla reguły `no_resolution` zawiera tylko ten
    numer.

    Wyłapuje raport, który zna samą liczbę odrzuceń: bez numerów nie da się zajrzeć do odrzuconych
    zgłoszeń i sprawdzić, czy reguła miała rację."""
    report = filter_tickets([_ticket(ticket_id="19596", solution="brak"), _ticket(ticket_id="2")])

    assert report.ticket_ids_for("no_resolution") == ["19596"]


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

    Wyłapuje zniknięcie tego ostrzeżenia. Reguły czytają tekst pisany przez model, więc po zmianie
    promptu albo modelu mogą przestać pasować do czegokolwiek i same tego nie zauważą: każde
    zgłoszenie przechodzi, a żaden błąd się nie pojawia."""
    report = filter_tickets([_ticket(ticket_id=str(i)) for i in range(MIN_RECORDS_FOR_DROP_RATE)])

    assert "reguły" in (drop_rate_warning(report) or "")


def test_plausible_drop_rate_is_silent() -> None:
    """Sprawdza, czy filtr nie ostrzega, gdy odrzuca mniej więcej tyle, ile przewidują pomiary:
    w paczce o wielkości progu `MIN_RECORDS_FOR_DROP_RATE` jedna piąta zgłoszeń ma w rozwiązaniu
    samo „brak".

    Wyłapuje ostrzeżenie przy zdrowym przebiegu: alarm, który odzywa się zawsze, przestaje być
    czytany i nie pomoże wtedy, gdy reguły naprawdę zamilkną."""
    tickets = [_ticket(ticket_id=str(i)) for i in range(MIN_RECORDS_FOR_DROP_RATE)]
    # Roughly the measured 19%, comfortably inside the tolerance.
    for i in range(MIN_RECORDS_FOR_DROP_RATE // 5):
        tickets[i] = _ticket(ticket_id=str(i), solution="brak")

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
