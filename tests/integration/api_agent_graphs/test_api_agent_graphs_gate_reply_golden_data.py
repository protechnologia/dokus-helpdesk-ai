"""
Description:
Spójność zestawu bramki wysyłki na prawdziwych wiadomościach (`graph-gate-reply.json`, p. 33.3)
z wątkami korpusu, bez modelu i bez stacku. Wpis to wiadomość konsultanta: zgłoszenie, numer
komentarza, warstwa doboru, skrót wiadomości i łamane reguły z powodem. Na zestawie stoi test
bramki na żywym modelu, a pomyłka w nim nie daje błędu, tylko fałszywy wynik pomiaru.

| warunek                                                 | czym grozi jego brak                   |
|---------------------------------------------------------|----------------------------------------|
| liczniki w metryczce zgadzają się z wpisami             | metryczka, która kłamie o zestawie     |
| każde zgłoszenie raz, warstwa ze znanej listy           | sprawa liczona dwa razy albo w nicości |
| skrót zgadza się z wiadomością wyciętą z korpusu        | bramka oceniana na innym tekście, niż  |
|                                                         | widzieli oceniający                    |
| reguła z zestawu, każda raz i z powodem                 | etykieta, której nie da się sprawdzić  |
| wpis wątpliwy mówi, czego nie był pewny oceniający      | przegląd złych werdyktów bez punktu    |
|                                                         | zaczepienia                            |

Zestaw i korpus to dane klientów, poza repo, więc bez nich testy się pomija, a nie padają.
"""

import json
from collections import Counter

import pytest

from tests._helpers.golden_gate_reply import (
    ANONYMIZED_DIR,
    GOLDEN_FILE,
    STRATA,
    corpus_message,
    golden_gate_reply_cases,
    message_digest,
)

pytestmark = pytest.mark.skipif(
    not GOLDEN_FILE.is_file() or not ANONYMIZED_DIR.is_dir(),
    reason="zestawu bramki wysyłki i wątków korpusu nie ma w repo",
)

# Wpisy i metryczka zestawu; bez danych są puste, a testy pliku i tak pomija `pytestmark`.
CASES = golden_gate_reply_cases() if GOLDEN_FILE.is_file() else []
META  = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["meta"] if GOLDEN_FILE.is_file() else {}


def test_the_counts_in_the_header_match_the_entries() -> None:
    """Sprawdza, czy metryczka zestawu podaje tyle wpisów, ile ich jest, i tyle samo w każdej
    warstwie, przy każdym oczekiwanym werdykcie i przy każdej regule.

    Wyłapuje metryczkę, która kłamie o zestawie: po dopisaniu, usunięciu albo poprawieniu
    etykiety liczby w raporcie i w CLAUDE.md przestałyby się zgadzać z tym, co test mierzy."""
    counts = META["counts"]
    rules  = Counter(str(rule) for case in CASES for rule in case.broken_rules)

    assert counts["messages"] == len(CASES)
    assert counts["strata"] == dict(Counter(case.stratum for case in CASES))
    assert counts["expected"] == dict(Counter(case.expected for case in CASES))
    assert counts["rules"] == dict(sorted(rules.items()))


def test_every_ticket_stands_once_in_a_known_stratum() -> None:
    """Sprawdza, czy każde zgłoszenie daje zestawowi jedną wiadomość, a jej warstwa należy do
    znanej listy.

    Wyłapuje wiadomość dopisaną dwa razy (liczyłaby się podwójnie w fałszywych alarmach), dwie
    wiadomości z jednego wątku, które przeważyłyby jedną sprawę, albo literówkę w warstwie, przez
    którą wiadomość wypadłaby z liczenia."""
    ids = [case.ticket_id for case in CASES]

    assert len(ids) == len(set(ids))
    assert {case.stratum for case in CASES} <= set(STRATA)


@pytest.mark.parametrize("case", CASES, ids=[f"{case.ticket_id}/{case.comment}" for case in CASES])
def test_the_digest_matches_the_message_from_the_corpus(case) -> None:
    """Sprawdza, czy skrót wpisu zgadza się ze skrótem wiadomości konsultanta wyciętej
    z wątku korpusu pod zapisanym numerem komentarza.

    Wyłapuje wątek, który zmienił się od oznaczania (zamknięcie przez trasę nadpisuje plik
    w korpusie), zmienione wycinanie albo numer wskazujący komentarz klienta: bramka oceniałaby
    tekst, którego oceniający nie widzieli."""
    assert message_digest(corpus_message(case.ticket_id, case.comment)) == case.digest


def test_every_broken_rule_is_a_known_rule_with_a_reason() -> None:
    """Sprawdza, czy każda łamana reguła ma numer z zestawu reguł, pod który oznaczano, stoi
    przy wpisie raz i ma niepusty powód.

    Wyłapuje numer reguły spoza zestawu (przepuszczenie liczyłoby się przy regule, której nie
    ma), regułę wpisaną dwa razy albo etykietę bez uzasadnienia: przy niezgodności z bramką nie
    da się wtedy rozstrzygnąć, czy pomyliła się bramka, czy oceniający."""
    known = range(1, len(META["rules"]) + 1)

    for case in CASES:
        assert len(case.broken_rules) == len(set(case.broken_rules)), case.label
        assert all(violation.rule in known for violation in case.violations), case.label
        assert all(violation.reason.strip() for violation in case.violations), case.label


def test_a_doubtful_entry_says_what_was_in_doubt() -> None:
    """Sprawdza, czy wpis wątpliwy mówi, czego nie był pewny oceniający, a wpis pewny nie ma
    takiego opisu.

    Wyłapuje wpis oznaczony jako wątpliwy bez powodu: raport podaje złe werdykty przy wpisach
    wątpliwych osobno, a bez opisu przegląd takiego werdyktu zaczyna się od zera."""
    for case in CASES:
        assert bool(case.doubt and case.doubt.strip()) == case.doubtful, case.label
