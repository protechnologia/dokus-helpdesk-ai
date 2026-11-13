from pathlib import Path

import pytest

from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_service.writer_ticket_card import write_card_with_thread
from tests._helpers.tickets_index.samples import TICKET_ID, sample_card, sample_thread

# Wspólny zapis wątku i karty w korpusie, na katalogu tymczasowym. Wołają go trasa zamknięcia
# i masowy import; ich testy sprawdzają, kiedy go wołają, a ten — co i w jakiej kolejności pisze.


def test_the_thread_and_the_card_land_under_the_ticket_number(tmp_path: Path) -> None:
    """Sprawdza, czy zapis kładzie wątek w `anonymized/<numer>.txt` i kartę w `cards/<numer>.json`
    z treścią, z której da się odtworzyć to, co dostał, i mówi, że karty wcześniej nie było,
    a przy drugim zapisie, że była.

    Wyłapuje zapis pod złą nazwą albo w złym katalogu oraz zgubioną informację o zastąpieniu
    karty: indeks nie odbudowałby się z korpusu, a trasa nie powiedziałaby, że zgłoszenie
    zamknięto ponownie."""
    corpus = TicketsCorpus(root=tmp_path)

    first  = write_card_with_thread(corpus, sample_thread(), sample_card())
    second = write_card_with_thread(corpus, sample_thread(), sample_card())

    card = (tmp_path / "cards" / f"{TICKET_ID}.json").read_text(encoding="utf-8")

    assert (tmp_path / "anonymized" / f"{TICKET_ID}.txt").read_text(encoding="utf-8") == (
        sample_thread().text
    )
    assert ParsedTicket.model_validate_json(card) == sample_card()
    assert (first, second) == (False, True)


def test_no_card_is_written_when_the_thread_cannot_be(tmp_path: Path) -> None:
    """Sprawdza, czy gdy wątku nie da się zapisać (w miejscu pliku wątku stoi katalog), zapis
    kończy się błędem, a karty w korpusie nie ma.

    Wyłapuje kolejność, w której karta idzie przed wątkiem: po przerwanym zapisie karta leżałaby
    bez wątku, a indeksacja korpusu odmówiłaby całego przebiegu."""
    (tmp_path / "anonymized" / f"{TICKET_ID}.txt").mkdir(parents=True)

    with pytest.raises(OSError):
        write_card_with_thread(TicketsCorpus(root=tmp_path), sample_thread(), sample_card())

    assert not (tmp_path / "cards" / f"{TICKET_ID}.json").exists()
