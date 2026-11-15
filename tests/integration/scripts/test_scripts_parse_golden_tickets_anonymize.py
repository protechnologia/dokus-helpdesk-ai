"""
Description:
Komenda `anonymize` skryptu `scripts/parse_golden_tickets.py`: wątki zgłoszeń golden setu
z `raw-db/` jego korpusu po anonimizacji, zapisywane do `anonymized/` obok kart, z których
potem `reindex` buduje tabelę wątków golden setu. Testy idą na korpusie w katalogu
tymczasowym, z anonimizatorem, który zamienia zmyśloną osobę na znaczniki, więc widać, czy na
dysk trafił tekst po anonimizacji.
"""

from pathlib import Path

from parse_golden_tickets import anonymize_all, wanted_ids

from app.core_model.tickets.tickets_corpus import TicketsCorpus
from tests._helpers.tickets_import import write_export
from tests._helpers.tickets_index import ReplacingAnonymizer
from tests._helpers.tickets_index.samples import PERSON, PERSON_MARKERS


async def test_the_thread_is_written_after_anonymization(tmp_path: Path) -> None:
    """Sprawdza, czy wątek zgłoszenia trafia do `anonymized/<numer>.txt` korpusu golden setu
    w postaci po anonimizacji: z nagłówkiem zgłoszenia i ze znacznikami w miejscu osoby.

    Wyłapuje zapis surowego wątku (dane osobowe w katalogu, z którego buduje się tabela
    wyszukiwania) i zapis pod inną nazwą niż ta, której szuka indekser: `reindex` golden setu
    odmówiłby wtedy pracy, bo karty nie miałyby wątków."""
    write_export(tmp_path, 41002)
    corpus = TicketsCorpus(root=tmp_path)

    saved, errors = await anonymize_all(
        ["41002"], corpus, ReplacingAnonymizer(PERSON, PERSON_MARKERS), concurrency=2
    )
    thread = (corpus.anonymized_dir / "41002.txt").read_text(encoding="utf-8")

    assert (saved, errors) == (1, [])
    assert thread.startswith("ZGŁOSZENIE 41002")
    assert PERSON_MARKERS in thread
    assert PERSON not in thread


async def test_one_failed_ticket_is_listed_and_the_rest_written(tmp_path: Path) -> None:
    """Sprawdza, czy zgłoszenie, na którym anonimizator zawiódł, trafia na listę błędów z nazwą
    wyjątku i bez pliku, a pozostałe zgłoszenia mają swoje wątki.

    Wyłapuje przebieg, który staje na pierwszym chwilowym błędzie usługi, i taki, który
    zapisuje coś w miejsce nieudanego wątku: plik bez anonimizacji albo pusty wyglądałby jak
    zrobiony i następny przebieg by go pominął."""
    for ticket_id in (41002, 41003):
        write_export(tmp_path, ticket_id)

    corpus     = TicketsCorpus(root=tmp_path)
    anonymizer = ReplacingAnonymizer(PERSON, PERSON_MARKERS, fail_on="ZGŁOSZENIE 41003")

    saved, errors = await anonymize_all(["41002", "41003"], corpus, anonymizer, 2)

    assert (saved, errors) == (1, [("41003", "AnonymizationError")])
    assert sorted(path.name for path in corpus.anonymized_dir.iterdir()) == ["41002.txt"]


def test_tickets_with_a_written_thread_are_skipped() -> None:
    """Sprawdza, czy wybór zgłoszeń pomija te, których wątek już leży (tu 10170), liczy je
    tylko wśród zgłoszeń zestawu (plik 99999 spoza zestawu się nie liczy) i tnie listę limitem.

    Wyłapuje przebieg, który po przerwaniu zaczyna od nowa i płaci za wątki już zapisane, oraz
    licznik zrobionych zawyżony plikami, których zestaw nie zna."""
    all_ids = ["10012", "10170", "10233"]

    assert wanted_ids(all_ids, {"10170", "99999"}, None) == (["10012", "10233"], 3, 1)
    assert wanted_ids(all_ids, {"10170"}, 1) == (["10012"], 3, 1)
