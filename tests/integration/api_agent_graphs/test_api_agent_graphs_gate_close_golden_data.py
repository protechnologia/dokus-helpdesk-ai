"""
Description:
Spójność zestawu bramki zamknięcia na prawdziwych zamknięciach (`gate-close.json`, p. 33.2)
z wątkami korpusu, bez modelu i bez stacku. Wpis to zamknięcie: warstwa doboru, liczba
komentarzy w chwili zamknięcia, skrót uciętego wątku, rodzaj i dwie etykiety z powodem. Na
zestawie stoi test bramki na żywym modelu, a pomyłka w nim nie daje błędu, tylko fałszywy wynik
pomiaru.

| warunek                                                 | czym grozi jego brak                   |
|---------------------------------------------------------|----------------------------------------|
| liczniki w metryczce zgadzają się z wpisami             | metryczka, która kłamie o zestawie     |
| każde zgłoszenie raz, warstwa i rodzaj ze znanej listy  | sprawa liczona dwa razy albo w nicości |
| skrót zgadza się z wątkiem z korpusu uciętym na         | bramka oceniana na innym tekście, niż  |
| zamknięciu                                              | widzieli oceniający                    |
| przy każdej etykiecie powód                             | etykieta, której nie da się sprawdzić  |

Zestaw i korpus to dane klientów, poza repo, więc bez nich testy się pomija, a nie padają.
"""

import json
from collections import Counter

import pytest

from tests._helpers.golden_gate_close import (
    ANONYMIZED_DIR,
    GOLDEN_FILE,
    KINDS,
    STRATA,
    closing_thread,
    golden_gate_close_cases,
    thread_digest,
)

pytestmark = pytest.mark.skipif(
    not GOLDEN_FILE.is_file() or not ANONYMIZED_DIR.is_dir(),
    reason="zestawu bramki zamknięcia i wątków korpusu nie ma w repo",
)

# Wpisy zestawu; bez danych lista jest pusta, a testy pliku i tak pomija `pytestmark`.
CASES = golden_gate_close_cases() if GOLDEN_FILE.is_file() else []


def test_the_counts_in_the_header_match_the_entries() -> None:
    """Sprawdza, czy metryczka zestawu podaje tyle wpisów, ile ich jest, i tyle samo w każdej
    warstwie i każdym rodzaju.

    Wyłapuje metryczkę, która kłamie o zestawie: po dopisaniu albo usunięciu wpisu liczby
    w raporcie i w CLAUDE.md przestałyby się zgadzać z tym, co test mierzy."""
    counts = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["meta"]["counts"]

    assert counts["tickets"] == len(CASES)
    assert counts["strata"] == dict(Counter(case.stratum for case in CASES))
    assert counts["kinds"] == dict(Counter(case.kind for case in CASES))


def test_every_ticket_stands_once_in_a_known_stratum_and_kind() -> None:
    """Sprawdza, czy każde zgłoszenie stoi w zestawie raz, a jego warstwa i rodzaj należą do
    znanych list.

    Wyłapuje zgłoszenie dopisane dwa razy (liczyłoby się podwójnie w fałszywych alarmach) albo
    literówkę w warstwie czy rodzaju, przez którą sprawa wypadłaby z liczenia."""
    ids = [case.ticket_id for case in CASES]

    assert len(ids) == len(set(ids))
    assert {case.stratum for case in CASES} <= set(STRATA)
    assert {case.kind for case in CASES} <= set(KINDS)


@pytest.mark.parametrize("case", CASES, ids=[case.ticket_id for case in CASES])
def test_the_digest_matches_the_thread_cut_at_closing(case) -> None:
    """Sprawdza, czy skrót wpisu zgadza się ze skrótem wątku z korpusu uciętego po zapisanej
    liczbie komentarzy.

    Wyłapuje wątek, który zmienił się od oznaczania (zamknięcie przez trasę nadpisuje plik
    w korpusie) albo zmienione ucięcie: bramka oceniałaby tekst, którego oceniający nie
    widzieli."""
    assert thread_digest(closing_thread(case.ticket_id, case.comments_at_close)) == case.digest


def test_every_label_has_a_reason() -> None:
    """Sprawdza, czy przy każdej etykiecie stoi niepusty powód.

    Wyłapuje etykietę bez uzasadnienia: przy niezgodności z bramką nie da się wtedy
    rozstrzygnąć, czy pomyliła się bramka, czy oceniający."""
    assert all(case.problem_reason.strip() and case.action_reason.strip() for case in CASES)
