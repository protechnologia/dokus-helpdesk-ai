"""
Description:
Skrypt `scripts/build_mail_dictionary.py`: słownik szablonów kanału „Automat mailowy” z wątków
korpusu. Słownik zmyślony z repo porównuje się z budową z jego źródła, a reszta idzie na
korpusach w katalogu tymczasowym, z plikami eksportu zmyślonych zgłoszeń.
"""

from pathlib import Path

from build_mail_dictionary import build_templates, cli, mail_tickets
from typer.testing import CliRunner

from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_service.loader_mail_dictionary import TEMPLATES_FILE
from tests._helpers.mail import BUILD_COMMAND, SAFE_MAIL_DIR, safe_templates
from tests._helpers.tickets_import import write_export


def test_the_safe_dictionary_matches_its_source() -> None:
    """Sprawdza, czy słownik zmyślony z repo to dokładnie ten słownik, który skrypt buduje ze
    zmyślonych wątków obok niego, z tą samą długością ciągu i tym samym progiem.

    Wyłapuje słownik w repo, który rozjechał się ze źródłem po zmianie wątków albo sposobu
    liczenia skrótów: testy normalizera mierzyłyby wtedy słownik, którego nikt już nie zbuduje."""
    committed = safe_templates()
    rebuilt   = build_templates(
        mail_tickets(TicketsCorpus(root=SAFE_MAIL_DIR)),
        committed.run_words,
        committed.min_threads,
        committed.source,
        committed.built_on,
    )

    assert rebuilt == committed, f"słownik zmyślony jest nieaktualny: {BUILD_COMMAND}"


def test_only_mail_threads_are_read(tmp_path: Path) -> None:
    """Sprawdza, czy skrypt czyta z `raw-db/` korpusu tylko zgłoszenia kanału „Automat
    mailowy”, po numerze, a zgłoszenie z innej kategorii pomija.

    Wyłapuje liczenie wszystkich zgłoszeń korpusu: zwroty typowe dla zwykłych zgłoszeń
    weszłyby do słownika i znikałyby z wątków mailowych."""
    write_export(tmp_path, 41002, category="Automat mailowy")
    write_export(tmp_path, 41003, category="Błąd")
    write_export(tmp_path, 41001, category="Automat mailowy")

    tickets = mail_tickets(TicketsCorpus(root=tmp_path))

    assert [ticket.ticket_id for ticket in tickets] == ["41001", "41002"]


def test_a_corpus_without_mail_threads_fails_without_writing(tmp_path: Path) -> None:
    """Sprawdza, czy budowa z korpusu bez wątków kanału kończy się kodem 1 i nie zapisuje
    słownika.

    Wyłapuje zapis pustego słownika z błędnie wskazanego korpusu: zastąpiłby działający
    słownik i wyłączył po cichu usuwanie stopek."""
    write_export(tmp_path, 41003, category="Błąd")
    out_dir = tmp_path / "mail"

    result = CliRunner().invoke(cli, ["build", str(tmp_path), str(out_dir)])

    assert result.exit_code == 1
    assert not (out_dir / TEMPLATES_FILE).exists()
