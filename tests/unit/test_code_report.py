"""
Description:
Testy wczytania zestawu, cytowań z rozmowy, oceny sprawy i raportu scenariuszy cytowania kodu
(`tests/_helpers/scenarios/code/`), czyli tego, na czym stoi test cytowania kodu na żywym
modelu. Bez modelu — rozmowę i wynik grafu podaje test. Sprawy, uwagi i klocki rozmowy leżą
w `samples.py` helpera, więc tu stoją same testy.
"""

import json
from pathlib import Path

from app.agent_graphs.search.models import SearchNotes
from tests._helpers.scenarios.code import (
    CodeFragment,
    CodeReport,
    code_cases,
    code_quotes,
    code_sections,
    judge_code_case,
    listing_count,
    quoted_messages,
)
from tests._helpers.scenarios.code.samples import (
    CASE_IN_CODE,
    CASE_NOWHERE,
    CASE_THREAD,
    MAILBOX,
    NOTES,
    TEMPLATES,
    conversation,
    failed,
    quote,
    read_file,
    read_symbol,
    search_line,
)


def test_a_quote_of_lines_read_in_an_earlier_turn_counts_as_read() -> None:
    """Sprawdza, czy cytowanie linii, które odczyt pliku oddał w jednej z wcześniejszych tur, jest
    odczytane, a cytowania w kolejności rozmowy niosą fragment i rolę.

    Wyłapuje ocenę, która zwykłe cytowanie po przeczytaniu pliku liczy jako ślepe: test linii
    nieodczytanych padałby przy każdej poprawnej sprawie."""
    messages = conversation(
        [read_file("c1", TEMPLATES, 1, 33)],
        [quote("c2", TEMPLATES, 11, 25, "cause"), quote("c3", TEMPLATES, 26, 28, "excluded")],
    )

    quotes = code_quotes(messages)

    assert [(q.fragment.key, q.role, q.read) for q in quotes] == [
        (f"{TEMPLATES}:11-25", "cause", True),
        (f"{TEMPLATES}:26-28", "excluded", True),
    ]


def test_a_read_in_the_same_turn_as_the_quote_does_not_count() -> None:
    """Sprawdza, czy odczyt pliku z tej samej tury co cytowanie nie czyni cytowanych linii
    odczytanymi.

    Wyłapuje ocenę, która przepuszcza cytowanie zakresu wybranego, zanim model zobaczył linie:
    wywołania jednej tury model zgłasza naraz, przed wynikami."""
    messages = conversation(
        [read_file("c1", TEMPLATES, 1, 33), quote("c2", TEMPLATES, 11, 25, "cause")],
    )

    assert [quote.read for quote in code_quotes(messages)] == [False]


def test_a_quote_reaching_beyond_the_lines_read_is_unread() -> None:
    """Sprawdza, czy cytowanie, którego część linii leży poza odczytanym zakresem albo w innym
    pliku, jest nieodczytane.

    Wyłapuje ocenę, która sprawdza tylko pierwszą linię cytowania albo samą ścieżkę: model mógłby
    przeczytać kilka linii, a zacytować całą funkcję."""
    messages = conversation(
        [read_file("c1", TEMPLATES, 1, 20)],
        [quote("c2", TEMPLATES, 11, 25, "cause"), quote("c3", MAILBOX, 1, 5, "cause")],
    )

    assert [quote.read for quote in code_quotes(messages)] == [False, False]


def test_a_quote_of_exactly_the_lines_read_counts_as_read() -> None:
    """Sprawdza granice odczytanego zakresu: cytowanie od pierwszej do ostatniej linii odczytu
    pliku albo symbolu jest odczytane, a cytowanie sięgające jedną linię dalej — nie.

    Wyłapuje zakres odczytu liczony bez ostatniej linii albo z linią za nią: model, który
    zacytował dokładnie przeczytaną funkcję, wychodziłby na cytującego na ślepo, albo odwrotnie."""
    messages = conversation(
        [read_file("c1", TEMPLATES, 1, 20), read_symbol("c2", MAILBOX, 17, 32)],
        [
            quote("c3", TEMPLATES, 1, 20, "cause"),
            quote("c4", MAILBOX, 17, 32, "cause"),
            quote("c5", TEMPLATES, 20, 21, "cause"),
        ],
    )

    assert [quote.read for quote in code_quotes(messages)] == [True, True, False]


def test_a_symbol_read_counts_like_a_file_read() -> None:
    """Sprawdza, czy linie oddane przez odczyt symbolu liczą się jako odczytane, tak jak linie
    z odczytu pliku.

    Wyłapuje ocenę, która zna tylko odczyt pliku: model, który przeczytał funkcję w całości
    i ją zacytował, wychodziłby na cytującego na ślepo."""
    messages = conversation(
        [read_symbol("c1", TEMPLATES, 17, 32)],
        [quote("c2", TEMPLATES, 22, 26, "cause")],
    )

    assert [quote.read for quote in code_quotes(messages)] == [True]


def test_a_line_seen_only_in_a_search_result_is_unread() -> None:
    """Sprawdza, czy linia, którą model widział tylko w wyniku szukania, nie jest odczytana.

    Wyłapuje ocenę, która liczy trafienie szukania jako odczyt: model cytowałby przyczynę po
    jednej linii, bez otoczenia, które mówi, kiedy komunikat pada."""
    messages = conversation(
        [search_line("c1", TEMPLATES, 25)],
        [quote("c2", TEMPLATES, 25, 25, "cause")],
    )

    assert [quote.read for quote in code_quotes(messages)] == [False]


def test_failed_calls_neither_read_nor_quote() -> None:
    """Sprawdza, czy odczyt, na który narzędzie oddało błąd, niczego nie odczytuje, a cytowanie
    z błędem nie jest cytowaniem.

    Wyłapuje ocenę, która czyta argumenty wywołań zamiast wyników: odrzucone cytowanie
    liczyłoby się jako przyczyna, a odrzucony odczyt — jako przeczytane linie."""
    messages = conversation(
        [failed("c1", "read_code_file"), failed("c2", "quote_code")],
        [quote("c3", TEMPLATES, 11, 25, "cause")],
    )

    assert [(quote.fragment.key, quote.read) for quote in code_quotes(messages)] == [
        (f"{TEMPLATES}:11-25", False),
    ]


def test_listing_count_counts_every_listing_call() -> None:
    """Sprawdza, czy licznik spisów katalogu liczy każde wywołanie spisu, także to, na które
    narzędzie oddało błąd, i nie liczy innych narzędzi.

    Wyłapuje licznik, który gubi spis z błędem albo liczy wszystkie wywołania: raport mówiłby
    nieprawdę o tym, czy model po spis sięgnął."""
    messages = conversation(
        [failed("c1", "list_code_files"), read_file("c2", TEMPLATES, 1, 5)],
        [failed("c3", "list_code_files")],
    )

    assert listing_count(messages) == 2


def test_quoted_messages_are_the_texts_in_polish_quotes() -> None:
    """Sprawdza, czy komunikaty ze zgłoszenia to teksty w polskim cudzysłowie „…”, w kolejności
    w tekście.

    Wyłapuje wycinanie komunikatu razem z cudzysłowem albo tylko pierwszego z kilku: test
    zestawu szukałby w kodzie tekstu, którego tam nie ma."""
    text = "Pojawia się „Pierwszy komunikat”, a potem „Drugi”. Zwykłe \"cudzysłowy\" nie."

    assert quoted_messages(text) == ("Pierwszy komunikat", "Drugi")


def test_the_set_reader_fills_absent_fields_with_no_requirement(tmp_path: Path) -> None:
    """Sprawdza, czy wczytanie zestawu zamienia brak pól sprawy na brak wymogu: pustą listę
    plików, brak zakazu przyczyny, brak nazw i brak fragmentu, a fragment z zestawu — na
    `CodeFragment`.

    Wyłapuje wczytanie, które pada na sprawie bez opcjonalnego pola albo zamienia brak zakazu
    na zakaz: sprawa bez wymogów kończyłaby się wtedy błędem albo fałszywym czerwonym testem."""
    path = tmp_path / "code.json"
    body = {
        "meta":  {"name": "próba"},
        "cases": [
            {"id": "k09", "graphs": ["search"], "phenomenon": "bez wymogów",
             "finds_tickets_and_docs": True, "input": "ZGŁOSZENIE 9"},
            {"id": "k10", "graphs": ["search"], "phenomenon": "z fragmentem",
             "finds_tickets_and_docs": False,
             "should_not_quote_as_cause": {"path": MAILBOX, "from_line": 35, "to_line": 37},
             "input": "ZGŁOSZENIE 10"},
        ],
    }
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    bare, excluded = code_sections(path)["search"].cases

    assert bare.must_quote_as_cause == ()
    assert bare.must_not_quote_any_cause is False
    assert bare.notes_should_include == ()
    assert bare.should_not_quote_as_cause is None
    assert excluded.should_not_quote_as_cause == CodeFragment(MAILBOX, 35, 37)


def test_a_case_goes_into_the_section_of_every_graph_it_lists(tmp_path: Path) -> None:
    """Sprawdza, czy sprawa trafia do sekcji każdego grafu z pola `graphs`, sekcje stoją
    w kolejności pierwszego wystąpienia grafu, sprawy w sekcji — w kolejności zestawu, a lista
    wszystkich spraw ma każdą sprawę raz.

    Wyłapuje wczytanie, które bierze tylko pierwszy graf sprawy (sprawa nie szłaby na pozostałych)
    albo myli kolejność spraw, przez co raport i testy pokazywałyby je w innym porządku niż
    zestaw."""
    path = tmp_path / "code.json"
    body = {
        "meta":  {"name": "próba"},
        "cases": [
            {"id": "k01", "graphs": ["search", "suggest_questions"], "phenomenon": "obu",
             "finds_tickets_and_docs": False, "input": "ZGŁOSZENIE 1"},
            {"id": "k02", "graphs": ["search"], "phenomenon": "jednego",
             "finds_tickets_and_docs": False, "input": "ZGŁOSZENIE 2"},
        ],
    }
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")

    sections = code_sections(path)

    assert list(sections) == ["search", "suggest_questions"]
    assert [case.case_id for case in sections["search"].cases] == ["k01", "k02"]
    assert [case.case_id for case in sections["suggest_questions"].cases] == ["k01"]
    assert [case.case_id for case in code_cases(path)] == ["k01", "k02"]


def test_a_case_with_its_file_quoted_and_named_is_matching() -> None:
    """Sprawdza, czy sprawa, w której model przeczytał plik, zacytował go jako przyczynę i nazwał
    w uwagach nadmiarowy plik (w innej wielkości liter), jest zgodna, z plikiem przyczyny
    i spisem w ocenie.

    Wyłapuje ocenę, która nie widzi pliku przyczyny w poprawnej sprawie albo porównuje nazwę
    w uwagach z wielkością liter: czerwony test i licznik „brak” bez winy modelu."""
    messages = conversation(
        [read_file("c1", TEMPLATES, 1, 33), failed("c2", "list_code_files")],
        [quote("c3", TEMPLATES, 11, 25, "cause")],
    )

    outcome = judge_code_case(CASE_IN_CODE, SearchNotes(internal_notes=NOTES), messages, 0)

    assert outcome.assessment       == "zgodny"
    assert outcome.cause_files      == (TEMPLATES,)
    assert outcome.listings         == 1
    assert outcome.missing_in_notes == ()


def test_a_missing_file_and_a_cause_where_none_is_allowed_are_named() -> None:
    """Sprawdza, czy brak wymaganego pliku wśród przyczyn i przyczyna w sprawie, która żadnej nie
    dopuszcza, trafiają do oceny z nazwą pliku, a nazwa, której uwagi nie wymieniają, do
    licznika braków.

    Wyłapuje ocenę ślepą na jedną ze stron pary: model, który zawsze albo nigdy nie cytuje
    przyczyny, przeszedłby test drugiej strony."""
    read     = [read_file("c1", TEMPLATES, 1, 33)]
    excluded = conversation(read, [quote("c2", TEMPLATES, 11, 25, "excluded")])
    caused   = conversation(read, [quote("c2", TEMPLATES, 11, 25, "cause")])
    notes    = SearchNotes(internal_notes="## Kod aplikacji\n- nic")

    missing = judge_code_case(CASE_IN_CODE, notes, excluded, 0)
    stray   = judge_code_case(CASE_NOWHERE, notes, caused, 0)

    assert missing.missing_causes   == (TEMPLATES,)
    assert missing.missing_in_notes == ("wezwanie_stare",)
    assert missing.assessment       == f"BEZ PLIKU PRZYCZYNY: {TEMPLATES}"
    assert stray.stray_causes       == (TEMPLATES,)
    assert stray.assessment         == f"PRZYCZYNA Z LUŹNEGO PLIKU: {TEMPLATES}"


def test_an_unread_quote_is_named_in_the_assessment() -> None:
    """Sprawdza, czy cytowanie linii nieodczytanych trafia do oceny jako fragment z zakresem,
    obok zgodnego pliku przyczyny.

    Wyłapuje ocenę, która przy poprawnym pliku przyczyny przestaje sprawdzać, czy model linie
    przeczytał: cytowanie na ślepo przeszłoby, bo trafiło we właściwy plik."""
    messages = conversation([quote("c1", TEMPLATES, 11, 25, "cause")])

    outcome = judge_code_case(CASE_IN_CODE, SearchNotes(internal_notes=NOTES), messages, 0)

    assert outcome.unread     == (f"{TEMPLATES}:11-25",)
    assert outcome.assessment == f"CYTOWANIE LINII NIEODCZYTANYCH: {TEMPLATES}:11-25"


def test_the_fragment_not_to_quote_counts_only_when_quoted_as_cause() -> None:
    """Sprawdza, czy fragment, którego model nie powinien cytować, liczy się tylko wtedy, gdy
    cytowanie w roli przyczyny na niego nachodzi, a cytowanie w roli wykluczenia albo obok niego
    się nie liczy.

    Wyłapuje licznik, który karze model za wskazanie wykluczonej przyczyny jako wykluczonej —
    a tak ma ją opisać — albo nie widzi cytowania, które nachodzi na fragment częściowo."""
    read     = [read_file("c1", MAILBOX, 1, 46)]
    excluded = conversation(
        read,
        [quote("c2", MAILBOX, 33, 38, "excluded"), quote("c3", MAILBOX, 25, 29, "cause")],
    )
    overlaps = conversation(read, [quote("c2", MAILBOX, 30, 35, "cause")])
    notes    = SearchNotes(internal_notes="## Kod aplikacji\n- blokada")

    assert not judge_code_case(CASE_THREAD, notes, excluded, 0).ruled_out_cause_quoted
    assert judge_code_case(CASE_THREAD, notes, overlaps, 0).ruled_out_cause_quoted


def test_a_rejected_answer_has_no_findings_and_no_fields() -> None:
    """Sprawdza, czy sprawa bez wyniku — węzeł odpowiedzi nie przyjął jej mimo poprawki — jest
    odpowiedzią nie do przyjęcia, bez znalezisk i bez pól.

    Wyłapuje ocenę, która brak wyniku liczy jako sprawę bez przyczyny i zalicza ją w parze
    „nigdzie”, choć wdrożeniowiec dostałby błąd zamiast wyniku."""
    outcome = judge_code_case(CASE_NOWHERE, None, (), 1)

    assert outcome.rejected
    assert (outcome.cause_files, outcome.unread, outcome.stray_causes) == ((), (), ())
    assert outcome.fields     == {}
    assert outcome.assessment == "ODPOWIEDŹ NIE DO PRZYJĘCIA"


def test_the_report_counts_errors_and_prints_counters_and_notes() -> None:
    """Sprawdza, czy raport liczy błędy wśród spraw, których dotyczą, a pod każdą sprawą wypisuje
    liczniki — pliki przyczyny, spisy, nazwy w uwagach, wykluczony fragment — i uwagi w całości.

    Wyłapuje raport, w którym liczniki mieszają sprawy z wymogiem i bez, i taki, który gubi licznik
    sprawy albo uwagi — a tylko z nich widać, czy model odróżnił kod od instalacji klienta."""
    report = CodeReport()
    named  = SearchNotes(internal_notes=NOTES)
    empty  = SearchNotes(internal_notes="—")
    caused = conversation(
        [read_file("c1", TEMPLATES, 1, 33)],
        [quote("c2", TEMPLATES, 11, 25, "cause")],
    )
    mailed = conversation(
        [read_file("c1", MAILBOX, 1, 46)],
        [quote("c2", MAILBOX, 25, 29, "cause")],
    )

    report.record("search", judge_code_case(CASE_IN_CODE, named, caused, 0))
    report.record("search", judge_code_case(CASE_NOWHERE, empty, caused, 0))
    report.record("search", judge_code_case(CASE_THREAD, empty, mailed, 0))
    report.record("search", judge_code_case(CASE_NOWHERE, None, (), 1))

    assert report.lines() == [
        "search: bez pliku przyczyny w 0 z 2, przyczyna z luźnego pliku w 1 z 2, "
        "cytowania nieodczytane w 0 z 4, nie do przyjęcia 1",
        "    k01 komunikat tylko w kodzie: zgodny; poprawek 0",
        f"        przyczyny z kodu: {TEMPLATES}; spisów 0; w uwagach: wezwanie_stare",
        "        internal_notes: ## Kod aplikacji",
        "                        - RejestrSzablonow.php:11–25: plik Wezwanie_Stare.twig spoza "
        "listy typów",
        f"    k02 komunikatu nie ma nigdzie: PRZYCZYNA Z LUŹNEGO PLIKU: {TEMPLATES}; poprawek 0",
        f"        przyczyny z kodu: {TEMPLATES}; spisów 0",
        "        internal_notes: —",
        "    k03 wątek wyklucza załącznik: zgodny; poprawek 0",
        f"        przyczyny z kodu: {MAILBOX}; spisów 0; wykluczona przez wątek przyczyna "
        f"{MAILBOX}:35-37 zacytowana: nie",
        "        internal_notes: —",
        "    k02 komunikatu nie ma nigdzie: ODPOWIEDŹ NIE DO PRZYJĘCIA; poprawek 1",
    ]


def test_an_empty_report_prints_nothing() -> None:
    """Sprawdza, czy raport, do którego nikt niczego nie zgłosił, nie daje żadnej linii.

    Wyłapuje raport, który dopisywałby pustą sekcję do wyjścia każdego przebiegu bez żywego
    modelu."""
    assert CodeReport().lines() == []
