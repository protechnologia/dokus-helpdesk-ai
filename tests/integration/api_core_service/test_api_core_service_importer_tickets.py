from datetime import date
from pathlib import Path

import pytest

from app.agent_graphs import parse_ticket
from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_model.tickets.ticket_import_failure import TicketImportFailure
from app.core_model.tickets.tickets_import_report import TicketsImportReport
from app.core_service.importer_tickets import MAX_FAILURES_IN_ROW, TicketsImportAbortedError
from app.engine_anonymization import AnonymizationError, AnonymizedText
from app.engine_llm import LLMConfigError, LLMError
from tests._helpers.mail import copy_safe_mail_export
from tests._helpers.mail.samples import sample_cleaned_thread
from tests._helpers.tickets_import import COST_PER_TICKET, MODEL, CardLLM, importer_on, write_export
from tests._helpers.tickets_index import ReplacingAnonymizer, write_card, write_thread
from tests._helpers.tickets_index.samples import PERSON, PERSON_MARKERS, sample_card

# Serwis masowego importu na katalogu tymczasowym: pliki eksportu i korpusu naprawdę leżą na
# dysku, graf karty stoi na węzłach właściwych (anonimizacja, tura modelu, walidacja karty),
# a model i anonimizator to atrapy. Że prawdziwy model oddaje dobre karty, sprawdzają scenariusze
# na żywym modelu, nie ten plik.


def _anonymizer() -> ReplacingAnonymizer:
    """
    Description:
    Anonimizator, który zamienia zmyśloną osobę z plików eksportu na znaczniki.

    Example args:
        (brak)

    Example result:
        ReplacingAnonymizer("Anna Nowak", "{IMIĘ} {NAZWISKO}")
    """
    return ReplacingAnonymizer(PERSON, PERSON_MARKERS)


def _ignore(report: TicketsImportReport) -> None:
    """
    Description:
    Odbiorca postępu dla testów, które na postęp nie patrzą.

    Example args:
        report=TicketsImportReport(…)

    Example result:
        None
    """


async def test_closed_tickets_become_threads_and_cards(tmp_path: Path) -> None:
    """Sprawdza, czy dwa zamknięte zgłoszenia z eksportu zostawiają w korpusie wątek
    w `anonymized/` i kartę w `cards/` pod swoim numerem, a karta ma numer i datę zgłoszenia
    ze źródła (2026-08-20) i nazwę modelu, który ją zrobił.

    Wyłapuje import, który zapisuje pliki pod złym numerem, gubi wątek albo kartę, bierze numer
    czy datę od modelu zamiast ze źródła albo nie zapisuje, którym modelem powstała karta: indeks
    nie odbudowałby się z korpusu, a karty nie dałoby się przypisać do zgłoszenia."""
    write_export(tmp_path, 41002)
    write_export(tmp_path, 41003)

    await importer_on(tmp_path, CardLLM(), _anonymizer()).run(None, _ignore)

    for ticket_id in ("41002", "41003"):
        card = ParsedTicket.model_validate_json(
            (tmp_path / "cards" / f"{ticket_id}.json").read_text(encoding="utf-8")
        )

        assert (tmp_path / "anonymized" / f"{ticket_id}.txt").exists()
        assert (card.ticket_id, card.date) == (ticket_id, date(2026, 8, 20))
        assert card.parser_model == MODEL


async def test_the_model_and_the_corpus_get_the_anonymized_thread(tmp_path: Path) -> None:
    """Sprawdza, czy model dostaje wątek po anonimizacji, ze znacznikami zamiast zmyślonej osoby,
    i czy ten sam wątek trafia do `anonymized/`.

    Wyłapuje import, który omija anonimizację albo zapisuje w korpusie surowy wątek: dane osobowe
    poszłyby do zewnętrznego modelu, a potem do tabeli wyszukiwania."""
    write_export(tmp_path, 41002)
    llm = CardLLM()

    await importer_on(tmp_path, llm, _anonymizer()).run(None, _ignore)

    thread = (tmp_path / "anonymized" / "41002.txt").read_text(encoding="utf-8")

    assert PERSON not in llm.prompts[0]
    assert PERSON_MARKERS in llm.prompts[0]
    assert PERSON not in thread
    assert PERSON_MARKERS in thread


async def test_an_open_ticket_stays_out(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie w toku (`w_weryfikacji`) nie idzie do modelu ani do korpusu,
    a raport liczy je osobno: jedno w toku, jedno do zrobienia.

    Wyłapuje import, który parsuje niedokończone wątki: do korpusu trafiłyby karty bez
    rozstrzygnięcia, za które trzeba zapłacić."""
    write_export(tmp_path, 41001, status="w_weryfikacji")
    write_export(tmp_path, 41003)
    llm = CardLLM()

    report = await importer_on(tmp_path, llm, _anonymizer()).run(None, _ignore)

    assert sorted(path.stem for path in (tmp_path / "cards").iterdir()) == ["41003"]
    assert len(llm.prompts) == 1
    assert (report.files, report.skipped_open, report.todo) == (2, 1, 1)


async def test_a_mail_ticket_is_imported_with_a_cleaned_thread(tmp_path: Path) -> None:
    """Sprawdza, czy zamknięte zgłoszenie z kanału „Automat mailowy” idzie do modelu i do
    korpusu jako wątek oczyszczony: model dostaje wątek bez drugiej kopii maila, stopki i cytatu,
    a `anonymized/` trzyma ten sam wątek wzorcowy normalizera, po anonimizacji.

    Wyłapuje import, który dalej pomija ten kanał albo parsuje surowe maile: karty powstałyby
    z cytatów i stopek, a role z bazy podawałyby odpowiedzi konsultanta jako słowa klienta."""
    copy_safe_mail_export(tmp_path, 41101)
    llm = CardLLM()

    report = await importer_on(tmp_path, llm, _anonymizer()).run(None, _ignore)

    thread  = (tmp_path / "anonymized" / "41101.txt").read_text(encoding="utf-8")
    cleaned = sample_cleaned_thread().replace(PERSON, PERSON_MARKERS)

    assert (report.todo, report.parsed) == (1, 1)
    assert thread == cleaned
    assert cleaned in llm.prompts[0]


async def test_a_ticket_with_a_card_is_left_alone(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie, które ma już kartę w korpusie, nie idzie do modelu, jego karta
    zostaje bez zmian, a raport liczy je w `already_carded`.

    Wyłapuje import, który nie umie się wznowić albo cofa kartę z trasy zamknięcia do stanu
    z eksportu: przerwany przebieg płaciłby drugi raz, a nowsza karta zostałaby nadpisana."""
    write_export(tmp_path, 41002)
    write_export(tmp_path, 41003)
    kept = sample_card(ticket_id="41002", solution="Karta z trasy zamknięcia, nowsza niż eksport.")
    write_card(tmp_path, kept)
    llm = CardLLM()

    report = await importer_on(tmp_path, llm, _anonymizer()).run(None, _ignore)

    stored = (tmp_path / "cards" / "41002.json").read_text(encoding="utf-8")

    assert ParsedTicket.model_validate_json(stored) == kept
    assert [prompt for prompt in llm.prompts if "ZGŁOSZENIE 41002" in prompt] == []
    assert (report.already_carded, report.todo, report.parsed) == (1, 1, 1)


async def test_a_thread_without_a_card_is_written_again(tmp_path: Path) -> None:
    """Sprawdza, czy wątek bez karty, zostawiony przez przerwany zapis, zostaje nadpisany wątkiem
    z nowego przebiegu, a karta dochodzi obok.

    Wyłapuje import, który pomija zgłoszenie po samym wątku albo zostawia stary wątek obok nowej
    karty: karta stałaby wtedy na innym tekście niż ten, który czyta agent."""
    write_export(tmp_path, 41002)
    write_thread(tmp_path, "41002", AnonymizedText(text="wątek z przerwanego przebiegu"))

    await importer_on(tmp_path, CardLLM(), _anonymizer()).run(None, _ignore)

    thread = (tmp_path / "anonymized" / "41002.txt").read_text(encoding="utf-8")

    assert thread.startswith("ZGŁOSZENIE 41002")
    assert (tmp_path / "cards" / "41002.json").exists()


async def test_the_limit_takes_the_first_tickets_by_number(tmp_path: Path) -> None:
    """Sprawdza, czy limit 2 przy zgłoszeniach 9, 10 i 100 bierze 9 i 10, czyli pierwsze po
    numerze, a nie po kolejności napisów (wtedy byłyby 10 i 100).

    Wyłapuje próbę na `--limit`, która bierze zgłoszenia w przypadkowej kolejności: próbny
    przebieg nie byłby powtarzalny, a raport próby nie mówiłby, które zgłoszenia zrobiono."""
    for ticket_id in (100, 10, 9):
        write_export(tmp_path, ticket_id)

    report = await importer_on(tmp_path, CardLLM(), _anonymizer(), concurrency=1).run(2, _ignore)

    assert sorted(path.stem for path in (tmp_path / "cards").iterdir()) == ["10", "9"]
    assert report.todo == 2


async def test_a_failed_ticket_is_reported_and_the_rest_goes_on(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie, przy którym model zawiódł (`LLMError`), a drugie, przy którym
    zawiódł anonimizator (`AnonymizationError`), trafiają do raportu z numerem i nazwą błędu, bez
    plików w korpusie, a trzecie zgłoszenie dostaje kartę.

    Wyłapuje import, który staje przy pierwszej chwilowej awarii albo gubi ją po cichu: przebieg
    tysiąca zgłoszeń nie skończyłby się nigdy, albo nie byłoby wiadomo, co wznowić."""
    for ticket_id in (41002, 41003, 41004):
        write_export(tmp_path, ticket_id)
    llm = CardLLM(failures={
        "41003": LLMError("model nie odpowiedział"),
        "41004": AnonymizationError("anonimizator nie odpowiedział"),
    })

    report = await importer_on(tmp_path, llm, _anonymizer()).run(None, _ignore)

    assert sorted(report.failed, key=lambda failure: failure.ticket_id) == [
        TicketImportFailure(ticket_id="41003", error="LLMError"),
        TicketImportFailure(ticket_id="41004", error="AnonymizationError"),
    ]
    assert sorted(path.stem for path in (tmp_path / "cards").iterdir()) == ["41002"]
    assert sorted(path.stem for path in (tmp_path / "anonymized").iterdir()) == ["41002"]


async def test_a_configuration_error_stops_the_run(tmp_path: Path) -> None:
    """Sprawdza, czy błąd konfiguracji modelu (`LLMConfigError`) przy pierwszym zgłoszeniu
    kończy cały przebieg tym błędem, następne zgłoszenie nie rusza, a raport tego, co zdążyło
    się zrobić, i tak trafia do korpusu.

    Wyłapuje import, który traktuje zły klucz albo model jak chwilową awarię: przeszedłby przez
    cały eksport, zapisując same błędy, zamiast od razu powiedzieć, co poprawić."""
    write_export(tmp_path, 41002)
    write_export(tmp_path, 41003)
    llm = CardLLM(failures={"41002": LLMConfigError("brak klucza")})

    with pytest.raises(LLMConfigError):
        await importer_on(tmp_path, llm, _anonymizer(), concurrency=1).run(None, _ignore)

    assert not (tmp_path / "cards").exists()
    assert len(llm.prompts) == 1
    assert len(list(tmp_path.glob("import-*.json"))) == 1


async def test_the_report_counts_cost_usefulness_and_components(tmp_path: Path) -> None:
    """Sprawdza, czy raport po trzech kartach (jedna nieprzydatna, jedna z `component` „ePUAP”)
    liczy 3 karty, 2 przydatne, koszt trzech tur, rozkład `component` oraz podaje model i skrót
    promptu parsującego.

    Wyłapuje raport, który gubi koszt, ocenę przydatności albo rozkład pól: operator nie wiedziałby,
    ile kosztował przebieg i ile kart przejdzie filtr, a karty nie dałoby się przypisać do wersji
    promptu."""
    for ticket_id in (41002, 41003, 41004):
        write_export(tmp_path, ticket_id)
    llm = CardLLM(cards={
        "41003": {"useful": False, "useful_reason": "Formułka zamykająca."},
        "41004": {"component": "ePUAP"},
    })

    report = await importer_on(tmp_path, llm, _anonymizer()).run(None, _ignore)

    assert (report.parsed, report.useful) == (3, 2)
    assert report.cost_usd == pytest.approx(3 * COST_PER_TICKET)
    assert report.components == {"e-Doręczenia": 2, "ePUAP": 1}
    assert (report.model, report.prompt_digest) == (MODEL, parse_ticket.prompt_digest())


async def test_the_report_lands_in_the_corpus_without_ticket_text(tmp_path: Path) -> None:
    """Sprawdza, czy po przebiegu w katalogu korpusu leży plik raportu z tą samą treścią, którą
    serwis oddał, z chwilą końca, i bez tekstu zgłoszeń: bez zmyślonej osoby i bez opisu.

    Wyłapuje raport, który nie trafia na dysk albo niesie treść zgłoszeń: przebiegu nie dałoby
    się potem ocenić, a dane osobowe trafiłyby do pliku, który się czyta i przesyła."""
    write_export(tmp_path, 41002)

    report = await importer_on(tmp_path, CardLLM(), _anonymizer()).run(None, _ignore)

    [path] = tmp_path.glob("import-*.json")
    text   = path.read_text(encoding="utf-8")

    assert TicketsImportReport.model_validate_json(text) == report
    assert report.finished_at is not None
    assert PERSON not in text
    assert "przesyłki" not in text


async def test_progress_comes_after_selection_and_after_every_ticket(tmp_path: Path) -> None:
    """Sprawdza, czy wołający dostaje raport raz zaraz po wyborze zgłoszeń, z liczbą do zrobienia
    i zerem zrobionych, a potem po każdym z trzech zgłoszeń, z rosnącą liczbą zrobionych.

    Wyłapuje import, który milczy do końca albo melduje się nieregularnie: przebieg idzie godzinę
    w tle, a postęp i koszt są jedynym znakiem, że działa."""
    for ticket_id in (41002, 41003, 41004):
        write_export(tmp_path, ticket_id)
    seen: list[tuple[int, int]] = []

    def remember(report: TicketsImportReport) -> None:
        """
        Description:
        Zapisuje, ile zgłoszeń było do zrobienia i ile zrobiono, przy każdym meldunku.

        Example args:
            report=TicketsImportReport(todo=3, parsed=1, …)

        Example result:
            None
        """
        seen.append((report.todo, report.done))

    await importer_on(tmp_path, CardLLM(), _anonymizer()).run(None, remember)

    assert seen == [(3, 0), (3, 1), (3, 2), (3, 3)]


async def test_nothing_to_do_leaves_no_report(tmp_path: Path) -> None:
    """Sprawdza, czy przebieg bez zgłoszeń do zrobienia (jedno w toku) melduje się raz, nie woła
    modelu i nie zostawia pliku raportu.

    Wyłapuje import, który przy każdym wznowieniu już skończonego korpusu zostawia pusty raport:
    w katalogu korpusu przybywałoby plików bez treści."""
    write_export(tmp_path, 41001, status="w_weryfikacji")
    llm = CardLLM()

    report = await importer_on(tmp_path, llm, _anonymizer()).run(None, _ignore)

    assert report.todo == 0
    assert llm.prompts == []
    assert list(tmp_path.glob("import-*.json")) == []


async def test_a_corpus_without_the_export_is_refused(tmp_path: Path) -> None:
    """Sprawdza, czy korpus bez katalogu `raw-db/` kończy przebieg błędem `NotADirectoryError`.

    Wyłapuje import, który przy złym katalogu korpusu melduje „nic do zrobienia”: operator
    uznałby, że korpus jest kompletny, choć eksport leży gdzie indziej."""
    with pytest.raises(NotADirectoryError):
        await importer_on(tmp_path, CardLLM(), _anonymizer()).run(None, _ignore)


async def test_aclose_closes_the_anonymizer(tmp_path: Path) -> None:
    """Sprawdza, czy `aclose()` serwisu zamyka anonimizator, na którym stoi graf karty.

    Wyłapuje serwis, który zostawia otwarte połączenia do usługi `anonymizer` po skończonym
    przebiegu komendy."""
    anonymizer = _anonymizer()

    await importer_on(tmp_path, CardLLM(), anonymizer).aclose()

    assert anonymizer.closed is True



async def test_ten_failures_in_a_row_stop_the_run(tmp_path: Path) -> None:
    """Sprawdza, czy po 10 zgłoszeniach z rzędu zakończonych błędem przebieg staje błędem
    `TicketsImportAbortedError`, jedenaste zgłoszenie nie idzie do modelu, a raport z dziesięcioma
    błędami i tak trafia do korpusu.

    Wyłapuje import bez hamulca: gdy padnie pod z anonimizatorem albo dostawca modelu, przebieg
    przeleciałby przez całą resztę listy, zapisując same błędy, zamiast od razu powiedzieć, że
    padła zależność."""
    for ticket_id in range(1, 12):
        write_export(tmp_path, ticket_id)
    llm = CardLLM(failures={str(number): LLMError("pod nie odpowiada") for number in range(1, 12)})

    with pytest.raises(TicketsImportAbortedError):
        await importer_on(tmp_path, llm, _anonymizer(), concurrency=1).run(None, _ignore)

    [path] = tmp_path.glob("import-*.json")

    assert len(llm.prompts) == MAX_FAILURES_IN_ROW
    saved = TicketsImportReport.model_validate_json(path.read_text(encoding="utf-8"))

    assert len(saved.failed) == MAX_FAILURES_IN_ROW


async def test_a_saved_card_resets_the_failure_count(tmp_path: Path) -> None:
    """Sprawdza, czy 9 błędów, potem udana karta i znowu 9 błędów nie zatrzymują przebiegu:
    wszystkie 19 zgłoszeń przechodzi, z 18 błędami i jedną kartą.

    Wyłapuje hamulec, który liczy wszystkie błędy zamiast błędów z rzędu: przebieg tysiąca
    zgłoszeń stanąłby po dziesiątej pojedynczej, chwilowej awarii."""
    for ticket_id in range(1, 20):
        write_export(tmp_path, ticket_id)
    failures = {str(number): LLMError("chwilowa awaria") for number in range(1, 20) if number != 10}
    llm      = CardLLM(failures=failures)

    report = await importer_on(tmp_path, llm, _anonymizer(), concurrency=1).run(None, _ignore)

    assert (report.parsed, len(report.failed)) == (1, 18)
