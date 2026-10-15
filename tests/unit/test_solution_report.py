"""
Description:
Testy wczytania zestawu, kart sprawy, dopasowania faktów, oceny sprawy i raportu scenariuszy
rozwiązania (`tests/_helpers/scenarios/solution/`), czyli tego, na czym stoi test rozwiązania na
żywym modelu. Bez modelu — wynik grafu podaje test, a próbki leżą w `samples.py` helpera.
"""

import json
from pathlib import Path

from tests._helpers.scenarios.solution import (
    SolutionReport,
    case_cards,
    judge_solution_case,
    mentions,
    mentions_all,
    question_marks,
    solution_sections,
)
from tests._helpers.scenarios.solution.samples import (
    BARE,
    CASE_DONE,
    CASE_STEP,
    CASE_WARNING,
    NOTES_ONLY,
    QUESTIONED,
    WARNED,
)


def test_a_fact_stands_when_any_variant_stands_regardless_of_case_letters_and_spaces() -> None:
    """Sprawdza, czy fakt stoi w tekście, gdy stoi w nim którykolwiek z wariantów, porównany bez
    wielkich liter, polskich znaków i odstępów, a nie stoi, gdy nie ma żadnego.

    Wyłapuje porównanie dosłowne: model, który napisał „Nie da sie usunac” albo „NIEODWRACALNE”,
    wychodziłby na gubiącego ostrzeżenie, a test padałby bez winy modelu."""
    fact = ("nieodwracaln", "nie da się usunąć")

    assert mentions("Takich wpisów NIE DA SIE usunac.", fact)
    assert mentions("To działanie jest NIEODWRACALNE.", fact)
    assert not mentions("Wpisy można później poprawić.", fact)


def test_a_mention_needs_every_fact_at_once() -> None:
    """Sprawdza, czy wzmianka stoi w tekście dopiero wtedy, gdy stoją w nim wszystkie jej fakty
    naraz, a jeden fakt nie wystarcza.

    Wyłapuje licznik, który bierze sam „operator” za krok ręcznego odbioru: każde zdanie
    o operatorze liczyłoby się jako powtórzenie kroku, który klient już wykonał."""
    facts = (("ręczn",), ("operator",))

    assert mentions_all("Prosimy odebrać przesyłkę ręcznie u operatora.", facts)
    assert not mentions_all("Prosimy zgłosić sprawę operatorowi.", facts)


def test_a_text_with_every_required_fact_is_matching() -> None:
    """Sprawdza, czy treść dla klienta z każdym faktem wymaganym jest zgodna, bez braków.

    Wyłapuje ocenę z fałszywym alarmem na poprawnej propozycji, na przykład przez polskie znaki
    albo wielkie litery w treści."""
    outcome = judge_solution_case(CASE_WARNING, WARNED, ("tickets:90002",), 0)

    assert outcome.missing    == ()
    assert outcome.text_given is True
    assert outcome.assessment == "zgodny"


def test_a_missing_fact_is_named_by_its_first_variant() -> None:
    """Sprawdza, czy brakujący fakt jest w ocenie nazwany swoim pierwszym wariantem, a fakt, który
    w treści stoi, w ocenie się nie pojawia.

    Wyłapuje ocenę, która nie mówi, czego brakuje: z raportu nie dałoby się poznać, czy model
    zgubił krok, czy jego nieodwracalność."""
    outcome = judge_solution_case(CASE_WARNING, BARE, ("tickets:90002",), 0)

    assert outcome.missing    == ("nieodwracaln",)
    assert outcome.assessment == "BRAK W TREŚCI: nieodwracaln"


def test_notes_without_a_client_text_carry_no_fact() -> None:
    """Sprawdza, czy wynik z samymi uwagami nie spełnia żadnego faktu, choć słowa faktów stoją
    w uwagach, i czy ocena mówi, że treści dla klienta nie ma.

    Wyłapuje ocenę, która liczy uwagi dla wdrożeniowca jak treść dla klienta: ostrzeżenie
    w uwagach do klienta nie dociera, a test przeszedłby."""
    outcome = judge_solution_case(CASE_WARNING, NOTES_ONLY, (), 0)

    assert outcome.text_given is False
    assert outcome.missing    == ("ponowne pobr", "nieodwracaln")
    assert outcome.assessment == "BEZ TREŚCI DLA KLIENTA"


def test_a_rejected_answer_has_no_findings_and_no_fields() -> None:
    """Sprawdza, czy sprawa bez wyniku — węzeł odpowiedzi nie przyjął jej mimo poprawki — jest
    odpowiedzią nie do przyjęcia, bez braków, bez liczników i bez pól.

    Wyłapuje ocenę, która brak wyniku liczy jako brak faktów: to osobny rodzaj porażki, po której
    wdrożeniowiec dostaje błąd, i ma osobny test."""
    outcome = judge_solution_case(CASE_WARNING, None, (), 1)

    assert outcome.rejected
    assert outcome.questions         == 0
    assert outcome.missing           == ()
    assert outcome.expected_mention  is None
    assert outcome.forbidden_mention is None
    assert outcome.fields            == {}
    assert outcome.assessment        == "ODPOWIEDŹ NIE DO PRZYJĘCIA"


def test_mention_counters_are_counted_only_where_the_case_asks_for_them() -> None:
    """Sprawdza, czy wzmianka oczekiwana i niepożądana są liczone tylko w sprawie, która je
    wymienia, a w pozostałych mają wartość „nie liczona”.

    Wyłapuje raport, w którym przy każdej sprawie stoi „brak” wzmianki, której sprawa nie
    sprawdza: licznik wyglądałby jak wynik, a niczego by nie mierzył."""
    done = judge_solution_case(CASE_DONE, BARE, (), 0)
    step = judge_solution_case(CASE_STEP, WARNED, (), 0)

    assert (done.forbidden_mention, done.expected_mention) == (True, None)
    assert (step.expected_mention, step.forbidden_mention) == (False, None)


def test_the_report_counts_missing_facts_and_prints_counters_and_fields() -> None:
    """Sprawdza, czy raport liczy sprawy bez faktu z karty wśród spraw, które fakty wymagają,
    i odpowiedzi nie do przyjęcia, a pod każdą sprawą z wynikiem wypisuje źródła, liczniki
    wzmianek i pola wyniku.

    Wyłapuje raport, w którym liczniki mieszają sprawy, i taki, z którego nie da się przeczytać
    treści propozycji — a tylko ona pokazuje, jak model napisał ostrzeżenie."""
    report  = SolutionReport()
    warning = judge_solution_case(CASE_WARNING, BARE, ("tickets:90002",), 0)
    done    = judge_solution_case(CASE_DONE, BARE, (), 0)
    failed  = judge_solution_case(CASE_STEP, None, (), 1)

    report.record("suggest_solution", warning)
    report.record("suggest_solution", done)
    report.record("suggest_solution", failed)

    assert report.lines() == [
        "suggest_solution: brak faktów z karty w 1 z 1, nie do przyjęcia 1, "
        "pytania w treści w 0 z 2",
        "    r03 krok nieodwracalny z karty: BRAK W TREŚCI: nieodwracaln; poprawek 0",
        "        źródła: tickets:90002; pytania w treści: 0",
        "        text: Kroki do wykonania:",
        "              1. Prosimy odebrać przesyłkę ręcznie u operatora; ponowne pobranie "
        "uruchomimy po naszej stronie.",
        "        internal_notes: ",
        "    r01 krok już wykonany: zgodny; poprawek 0",
        "        źródła: —; wzmianka niepożądana: jest; pytania w treści: 0",
        "        text: Kroki do wykonania:",
        "              1. Prosimy odebrać przesyłkę ręcznie u operatora; ponowne pobranie "
        "uruchomimy po naszej stronie.",
        "        internal_notes: ",
        "    r02 krok z karty: ODPOWIEDŹ NIE DO PRZYJĘCIA; poprawek 1",
    ]


def test_only_questions_to_the_client_are_counted() -> None:
    """Sprawdza, czy licznik pytań liczy znaki zapytania w treści dla klienta, a pomija ten
    w cytacie komunikatu z ekranu „…”, w adresie z parametrami i w uwagach dla wdrożeniowca.

    Wyłapuje licznik, który bierze każdy znak zapytania: propozycja cytująca komunikat „Czy
    zapisać zmiany?” albo podająca adres z wyszukiwaniem wyglądałaby na pytanie do klienta,
    a pytanie zapisane w uwagach — na pytanie w treści, której klient nie dostanie."""
    outcome = judge_solution_case(CASE_STEP, QUESTIONED, (), 0)

    assert question_marks(QUESTIONED.text) == 1
    assert outcome.questions              == 1


def test_the_report_counts_cases_with_a_question_to_the_client() -> None:
    """Sprawdza, czy raport liczy w linii grafu sprawy z pytaniem w treści dla klienta wśród
    spraw z wynikiem i wypisuje liczbę pytań przy sprawie.

    Wyłapuje raport, który gubi licznik pytań albo liczy w mianowniku sprawy bez wyniku: nie
    dałoby się zobaczyć, że propozycja rozwiązania zamieniła się w pytania do klienta."""
    report = SolutionReport()

    report.record("suggest_solution", judge_solution_case(CASE_STEP, QUESTIONED, (), 0))
    report.record("suggest_solution", judge_solution_case(CASE_DONE, None, (), 1))

    lines = report.lines()

    assert lines[0].endswith("pytania w treści w 1 z 1")
    assert "        źródła: —; wzmianka oczekiwana: brak; pytania w treści: 1" in lines


def test_an_empty_report_prints_nothing() -> None:
    """Sprawdza, czy raport, do którego nikt niczego nie zgłosił, nie daje żadnej linii.

    Wyłapuje raport, który dopisywałby pustą sekcję do wyjścia każdego przebiegu bez żywego
    modelu."""
    assert SolutionReport().lines() == []


def test_the_set_reader_fills_absent_fields_with_no_requirement(tmp_path: Path) -> None:
    """Sprawdza, czy wczytanie zestawu zamienia brak pól sprawy na brak wymogu: brak zmian kart
    i puste listy faktów, a listy faktów z zestawu — na krotki wariantów.

    Wyłapuje wczytanie, które pada na sprawie bez opcjonalnego pola albo gubi warianty faktu:
    sprawa bez wymogów kończyłaby się błędem, a fakt z jednym wariantem zamiast kilku dawałby
    fałszywe braki."""
    path = tmp_path / "solution.json"
    body = {
        "meta":             {"name": "próba"},
        "suggest_solution": {"cases": [
            {"id": "r09", "phenomenon": "bez wymogów", "input": "ZGŁOSZENIE 9"},
            {"id": "r10", "phenomenon": "z faktami", "input": "ZGŁOSZENIE 10",
             "card_changes": {"90002": {"cause": "inna"}},
             "must_mention": [["nieodwracaln", "trwale"]], "should_mention": [["ręczn"]]},
        ]},
    }
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    bare, full = solution_sections(path)["suggest_solution"].cases

    assert (bare.card_changes, bare.must_mention, bare.should_not_mention) == ({}, (), ())
    assert full.card_changes   == {"90002": {"cause": "inna"}}
    assert full.must_mention   == (("nieodwracaln", "trwale"),)
    assert full.should_mention == (("ręczn",),)


def test_card_changes_replace_only_the_named_fields_of_the_named_card() -> None:
    """Sprawdza, czy karty sprawy to wbudowane karty atrap, w których zmieniono wyłącznie pola
    wskazane w `card_changes` wskazanej karty, a pozostałe karty i pola zostają bez zmian.

    Wyłapuje zmianę, która trafia do złej karty albo kasuje resztę jej pól: model czytałby
    materiał inny niż ten, który sprawa opisuje."""
    cards = {card.ticket_id: card for card in case_cards(CASE_WARNING)}
    plain = {card.ticket_id: card for card in case_cards(CASE_DONE)}

    assert cards["90002"].solution == "…"
    assert cards["90002"].cause    == plain["90002"].cause
    assert cards["90001"]          == plain["90001"]
