"""
Description:
Testy wczytania zestawu, liczników, oceny sprawy i raportu scenariuszy czytania znalezionego
materiału (`tests/_helpers/scenarios/reading/`), czyli tego, na czym stoi test czytania na żywym
modelu. Bez modelu — wynik grafu i rozmowę podaje test, a próbki leżą w `samples.py` helpera.
"""

import json
from pathlib import Path

from app.engine_llm import ChatMessage
from tests._helpers.scenarios.reading import (
    ReadingReport,
    code_calls,
    excluded_in_notes,
    judge_reading_case,
    material_units,
    reading_cases,
    reading_sections,
)
from tests._helpers.scenarios.reading.samples import (
    CARDS,
    CASE_CAUSES,
    CASE_DOCS,
    CASE_EXCLUDED,
    CASE_ORGANIZATIONAL,
    NOTES_EXCLUDED,
    NOTES_LISTED,
    NOTES_NEGATED,
    NOTES_PARAPHRASED,
    NOTES_SHORT,
    PROPOSAL,
    code_turn,
)


def test_the_set_reader_fills_absent_fields_with_no_requirement(tmp_path: Path) -> None:
    """Sprawdza, czy wczytanie zestawu zamienia brak pól sprawy na brak wymogu — puste listy
    kluczy i faktów oraz `False` przy kodzie — a pola podane czyta: klucze, fakty jako krotki
    wariantów i zakaz kodu.

    Wyłapuje wczytanie, które pada na sprawie bez opcjonalnego pola, gubi warianty faktu albo
    nie czyta zakazu kodu: sprawa organizacyjna nie byłaby wyróżniona w raporcie."""
    path = tmp_path / "reading.json"
    body = {
        "meta":  {"name": "próba"},
        "cases": [
            {"id": "c08", "graphs": ["search"], "phenomenon": "bez wymogów",
             "input": "ZGŁOSZENIE 8"},
            {"id": "c09", "graphs": ["search"], "phenomenon": "z wymogami",
             "input": "ZGŁOSZENIE 9", "must_read": ["tickets:90001"],
             "should_read": ["docs:a"], "should_not_read": ["docs:b"],
             "should_name": [["kolejk"]], "should_exclude": [["załącznik", "limit"]],
             "should_not_call_code": True},
        ],
    }
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    bare, full = reading_cases(path)

    assert (bare.must_read, bare.should_read, bare.should_not_read) == ((), (), ())
    assert (bare.should_name, bare.should_exclude, bare.should_not_call_code) == ((), (), False)
    assert (full.must_read, full.should_read, full.should_not_read) == (
        ("tickets:90001",), ("docs:a",), ("docs:b",),
    )
    assert full.should_name          == (("kolejk",),)
    assert full.should_exclude       == (("załącznik", "limit"),)
    assert full.should_not_call_code is True


def test_a_case_goes_into_the_section_of_every_graph_it_lists(tmp_path: Path) -> None:
    """Sprawdza, czy sekcje zestawu powstają z pola `graphs` spraw: sprawa idzie do sekcji
    każdego grafu, który wymienia, w kolejności zestawu, a graf bez spraw sekcji nie ma.

    Wyłapuje sekcje składane z pierwszego grafu sprawy albo w złej kolejności: sprawa nie
    poszłaby na grafie, który wymienia, a raport pomieszałby kolejność spraw."""
    path = tmp_path / "reading.json"
    body = {
        "cases": [
            {"id": "c01", "graphs": ["search", "suggest_solution"], "phenomenon": "a",
             "input": "ZGŁOSZENIE 1"},
            {"id": "c02", "graphs": ["search"], "phenomenon": "b", "input": "ZGŁOSZENIE 2"},
        ],
    }
    path.write_text(json.dumps(body), encoding="utf-8")

    sections = reading_sections(path)

    assert list(sections) == ["search", "suggest_solution"]
    assert [case.case_id for case in sections["search"].cases]           == ["c01", "c02"]
    assert [case.case_id for case in sections["suggest_solution"].cases] == ["c01"]


def test_material_units_join_card_and_thread_of_a_ticket_and_keep_sections_apart() -> None:
    """Sprawdza, czy materiał atrap po kluczu źródła łączy kartę i wątek jednego zgłoszenia pod
    jednym kluczem, ma też zgłoszenie z samym wątkiem, bez karty, i sekcję dokumentacji z treścią.

    Wyłapuje materiał bez wątków: wariant faktu, który stoi w cudzym wątku — „limit” przy
    limitach zasobów w wątku 90011 — przeszedłby test spójności zestawu, a licznik wykluczenia
    liczyłby linię o tamtej sprawie."""
    units = material_units()

    assert "Zacięta kolejka" in units["tickets:90001"]
    assert "ZGŁOSZENIE 90001" in units["tickets:90001"]
    assert "limity zasobów" in units["tickets:90011"]
    assert "ponownym zalogowaniu" in units["docs:adm-kancelaria-edoreczenia"]


def test_a_case_with_every_required_source_read_is_matching() -> None:
    """Sprawdza, czy sprawa, w której na liście źródeł stoją wszystkie wymagane karty, jest
    zgodna, bez nieprzeczytanych.

    Wyłapuje ocenę z fałszywym alarmem na poprawnym przebiegu, na przykład porównującą klucze
    w innym kształcie niż lista źródeł ze stanu grafu."""
    outcome = judge_reading_case(CASE_CAUSES, NOTES_EXCLUDED, CARDS, (), 0)

    assert outcome.unread     == ()
    assert outcome.assessment == "zgodny"


def test_a_card_found_but_not_read_is_named_in_the_assessment() -> None:
    """Sprawdza, czy wymagana karta, której nie ma na liście źródeł, trafia do nieprzeczytanych
    i jest nazwana w ocenie, a karty przeczytane nie.

    Wyłapuje ocenę, która nie mówi, czego model nie przeczytał: z raportu nie dałoby się poznać,
    którą przyczynę wynik pominął."""
    outcome = judge_reading_case(CASE_CAUSES, NOTES_EXCLUDED, CARDS[:2], (), 0)

    assert outcome.unread     == ("tickets:90003",)
    assert outcome.assessment == "NIEPRZECZYTANE: tickets:90003"


def test_facts_count_in_any_text_field_without_polish_letters() -> None:
    """Sprawdza, czy fakt do nazwania liczy się, gdy stoi w którymkolwiek polu tekstowym wyniku —
    w uwagach albo w treści dla klienta — także zapisany bez polskich znaków i wielkimi literami.

    Wyłapuje licznik, który patrzy tylko na jedno pole albo porównuje dosłownie: przyczyna
    nazwana w treści dla klienta albo „zalacznik” bez ogonków wyglądałyby na pominięte."""
    causes  = judge_reading_case(CASE_CAUSES, NOTES_EXCLUDED, CARDS, (), 0)
    relogin = judge_reading_case(CASE_DOCS, PROPOSAL, (), (), 0)

    assert causes.named  == ("kolejk", "blokad", "załącznik")
    assert relogin.named == ("zalog",)


def test_an_excluded_cause_needs_the_exclusion_word_in_the_same_line() -> None:
    """Sprawdza, czy przyczyna liczy się jako wykluczona, gdy w jednej linii uwag stoi jej nazwa
    i słowo wykluczenia (bez względu na wielkość liter, także po przysłówku kończącym się na
    „nie”), a nie liczy się, gdy nazwa stoi na liście spraw, a słowo — w innej linii.

    Wyłapuje licznik, który bierze całe uwagi naraz — każda przyczyna z listy spraw wyglądałaby
    na wykluczoną, bo gdzieś w uwagach pada „wyklucza” — i taki, który „jednoznacznie wyklucza”
    bierze za zaprzeczenie."""
    facts = CASE_EXCLUDED.should_exclude

    assert excluded_in_notes(NOTES_EXCLUDED.internal_notes, facts) == ("90003",)
    assert excluded_in_notes(NOTES_LISTED.internal_notes, facts)   == ()


def test_an_exclusion_in_the_words_of_the_model_counts() -> None:
    """Sprawdza, czy linia, w której model wyklucza przyczynę własnymi słowami — „wyklucza
    wariant dużego załącznika”, bez numeru sprawy — liczy się jako wykluczenie, choć w tej samej
    linii stoi „nie wyklucza” przy innych przyczynach.

    Wyłapuje licznik, który zna tylko słowa z materiału albo odrzuca całą linię po pierwszym
    zaprzeczeniu: w przebiegu na żywym modelu raport pokazał przez to brak wykluczenia, którego
    model dokonał wprost."""
    facts = CASE_EXCLUDED.should_exclude

    assert excluded_in_notes(NOTES_PARAPHRASED.internal_notes, facts) == ("90003",)


def test_a_negated_exclusion_does_not_count() -> None:
    """Sprawdza, czy linia ze słowem wykluczenia z zaprzeczeniem tuż przed nim — „nie wyklucza”,
    „niewykluczony” — nie liczy przyczyny jako wykluczonej.

    Wyłapuje licznik, który w pierwszych przebiegach na żywym modelu pokazywał wykluczenie na
    linii mówiącej, że przyczyny NIE wykluczono: raport przypisywał modelowi wniosek odwrotny do
    tego, który napisał."""
    facts = CASE_EXCLUDED.should_exclude

    assert excluded_in_notes(NOTES_NEGATED.internal_notes, facts) == ()


def test_wanted_and_unwanted_sections_are_counted_from_the_sources() -> None:
    """Sprawdza, czy sekcja oczekiwana i niepożądana liczą się tylko wtedy, gdy stoją na liście
    źródeł, i każda trafia do swojego licznika.

    Wyłapuje liczniki zamienione miejscami albo liczone z deklaracji modelu: dystraktor
    przeczytany zamiast właściwej sekcji wyglądałby w raporcie na sukces."""
    both = ("docs:adm-kancelaria-edoreczenia", "docs:adm-kancelaria-epuap")

    right = judge_reading_case(CASE_DOCS, PROPOSAL, both[:1], (), 0)
    wrong = judge_reading_case(CASE_DOCS, PROPOSAL, both[1:], (), 0)

    assert (right.read_wanted, right.read_unwanted) == (both[:1], ())
    assert (wrong.read_wanted, wrong.read_unwanted) == ((), both[1:])


def test_only_calls_of_code_tools_are_counted() -> None:
    """Sprawdza, czy licznik narzędzi kodu liczy wyłącznie wywołania narzędzi kodu w turach
    modelu, a wywołania innych narzędzi i wiadomości bez wywołań pomija.

    Wyłapuje licznik, który liczy każde wywołanie: sprawa organizacyjna, w której model tylko
    przeczytał instrukcję, wyglądałaby na sięganie po kod."""
    messages = [
        ChatMessage(role="user", content="ZGŁOSZENIE 90964"),
        code_turn(("find_code_text", "read_docs")),
        code_turn(("describe_code",)),
    ]

    assert code_calls(messages) == 2


def test_code_is_needless_only_in_a_case_without_code() -> None:
    """Sprawdza, czy wywołanie narzędzia kodu jest niepożądane w sprawie z zakazem kodu, a nie
    jest w sprawie bez zakazu ani w sprawie z zakazem, w której model po kod nie sięgnął.

    Wyłapuje wyróżnienie przy każdej sprawie z wywołaniem kodu — a w sprawie o działaniu
    aplikacji `search` ma kod sprawdzać — albo przy sprawie organizacyjnej bez wywołań."""
    calls = [code_turn(("find_code_text",))]

    assert judge_reading_case(CASE_ORGANIZATIONAL, NOTES_SHORT, (), calls, 0).needless_code
    assert not judge_reading_case(CASE_ORGANIZATIONAL, NOTES_SHORT, (), (), 0).needless_code
    assert not judge_reading_case(CASE_CAUSES, NOTES_SHORT, CARDS, calls, 0).needless_code


def test_a_rejected_answer_has_no_findings_and_no_fields() -> None:
    """Sprawdza, czy sprawa bez wyniku — węzeł odpowiedzi nie przyjął jej mimo poprawki — jest
    odpowiedzią nie do przyjęcia, bez nieprzeczytanych, liczników i pól.

    Wyłapuje ocenę, która brak wyniku liczy jako nieprzeczytany materiał: to osobny rodzaj
    porażki, po którym wdrożeniowiec dostaje błąd, i ma osobny test."""
    outcome = judge_reading_case(CASE_CAUSES, None, (), (), 1)

    assert outcome.rejected
    assert (outcome.unread, outcome.named, outcome.excluded) == ((), (), ())
    assert outcome.code_calls == 0
    assert outcome.fields     == {}
    assert outcome.assessment == "ODPOWIEDŹ NIE DO PRZYJĘCIA"


def test_the_report_counts_findings_and_prints_counters_and_fields() -> None:
    """Sprawdza, czy raport liczy nieprzeczytane wśród spraw, które materiał wymagają,
    odpowiedzi nie do przyjęcia i kod w sprawach bez kodu, a pod każdą sprawą z wynikiem
    wypisuje źródła, liczniki i pola wyniku.

    Wyłapuje raport, w którym liczniki mieszają sprawy, kod w sprawie organizacyjnej nie jest
    wyróżniony albo nie da się przeczytać uwag — a tylko one pokazują, jak model opisał
    przyczyny."""
    report   = ReadingReport()
    partial  = judge_reading_case(
        CASE_CAUSES, NOTES_SHORT, CARDS[:2], [code_turn(("find_code_text",))], 0,
    )
    training = judge_reading_case(
        CASE_ORGANIZATIONAL, NOTES_SHORT, (), [code_turn(("describe_code", "find_code_text"))], 0,
    )
    failed   = judge_reading_case(CASE_EXCLUDED, None, (), (), 1)

    report.record("search", partial)
    report.record("search", training)
    report.record("search", failed)

    assert report.lines() == [
        "search: nieprzeczytane w 1 z 2, nie do przyjęcia 1, kod niepożądany w 1 z 1",
        "    c01 trzy przyczyny: NIEPRZECZYTANE: tickets:90003; poprawek 0",
        "        źródła: tickets:90001, tickets:90002; nazwane 0 z 3; narzędzia kodu: 1",
        "        internal_notes: Przeczytane dwie sprawy.",
        "    c04 szkolenie: zgodny; poprawek 0",
        "        źródła: —; narzędzia kodu: 2 (powinno być 0)",
        "        internal_notes: Przeczytane dwie sprawy.",
        "    c02 wątek wyklucza załącznik: ODPOWIEDŹ NIE DO PRZYJĘCIA; poprawek 1",
    ]


def test_the_report_prints_section_and_exclusion_counters_when_the_case_has_them() -> None:
    """Sprawdza, czy linia liczników sprawy wypisuje nazwane fakty z ich nazwami, przyczyny
    wykluczone w uwagach oraz sekcje oczekiwane i niepożądane — każde tylko wtedy, gdy sprawa je
    liczy — a graf bez spraw z zakazem kodu nie ma licznika kodu niepożądanego.

    Wyłapuje raport, który gubi licznik sekcji albo wykluczenia, i taki, który przy każdym grafie
    dopisuje „kod niepożądany w 0 z 0”, licznik bez znaczenia."""
    report   = ReadingReport()
    excluded = judge_reading_case(CASE_EXCLUDED, NOTES_EXCLUDED, CARDS, (), 0)
    docs     = judge_reading_case(
        CASE_DOCS, PROPOSAL, ("docs:adm-kancelaria-epuap",), (), 0,
    )

    report.record("suggest_questions", excluded)
    report.record("suggest_questions", docs)

    lines = report.lines()

    assert lines[0] == "suggest_questions: nieprzeczytane w 0 z 1, nie do przyjęcia 0"
    assert (
        "        źródła: tickets:90001, tickets:90002, tickets:90003; nazwane 3 z 3: kolejk, "
        "blokad, załącznik; wykluczone w uwagach 1 z 1; narzędzia kodu: 0"
    ) in lines
    assert (
        "        źródła: docs:adm-kancelaria-epuap; nazwane 1 z 1: zalog; oczekiwane przeczytane "
        "0 z 1; niepożądane przeczytane 1 z 1; narzędzia kodu: 0"
    ) in lines


def test_an_empty_report_prints_nothing() -> None:
    """Sprawdza, czy raport, do którego nikt niczego nie zgłosił, nie daje żadnej linii.

    Wyłapuje raport, który dopisywałby pustą sekcję do wyjścia każdego przebiegu bez żywego
    modelu."""
    assert ReadingReport().lines() == []
