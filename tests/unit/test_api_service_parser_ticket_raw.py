import json
from datetime import date as Date
from pathlib import Path

import pytest

from app.service.parser_ticket_raw import load_raw_ticket


def _write_export(tmp_path: Path, **overrides) -> Path:
    """
    Description:
    Writes one export file shaped like `scripts/export_raw_tickets.py` produces, with overrides
    applied to the ticket part. Keeps each test to the one field it is about.

    Example args:
        tmp_path=Path("/tmp/pytest-0")
        overrides={"szczegolowy_opis": "<p>Opis</p>"}

    Example result:
        Path("/tmp/pytest-0/zgloszenie-33644.json")
    """
    ticket = {
        "id":               33644,
        "created_at":       "2026-06-23 11:45:05",
        "kategoria":        "Automat mailowy",
        "czego_dotyczy":    "Błąd wysyłki",
        "szczegolowy_opis": "<p>Nie działa wysyłka</p>",
    }
    ticket.update(overrides)

    payload = {
        "zrodlo":     "mysql_helpdesk_20260724-141140.sql",
        "tabela":     "zgloszenie",
        "zgloszenie": ticket,
        "komentarze": overrides.pop("komentarze", None) or [
            {
                "id":         34485,
                "typ":        "konczacy_zgloszenie",
                "autor_rola": "konsultant",
                "created_at": "2026-06-23 12:01:21",
                "tresc":      "<p>Zamykam</p>",
            }
        ],
    }

    path = tmp_path / "zgloszenie-33644.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    return path


def test_loads_identity_from_the_source(tmp_path: Path):
    """Plik eksportu → ticket_id i data ze źródła, nie z treści."""
    raw = load_raw_ticket(_write_export(tmp_path))

    assert raw.ticket_id == "33644"
    assert raw.date      == Date(2026, 6, 23)


def test_drops_the_time_of_day(tmp_path: Path):
    """Znacznik czasu MySQL → sama data; godzina nie trafia do artefaktu."""
    raw = load_raw_ticket(_write_export(tmp_path, created_at="2026-06-23 23:59:59"))

    assert raw.date == Date(2026, 6, 23)


def test_strips_html_from_every_text_field(tmp_path: Path):
    """Pola tekstowe → bez tagów już na wejściu, zanim zobaczy je prompt."""
    raw = load_raw_ticket(
        _write_export(tmp_path, czego_dotyczy="<b>Błąd</b>", szczegolowy_opis="<p>Opis</p>")
    )

    assert raw.subject          == "Błąd"
    assert raw.body             == "Opis"
    assert raw.comments[0].body == "Zamykam"


def test_keeps_the_source_category(tmp_path: Path):
    """Kategoria ze źródła — nie trafia do artefaktu, ale wskazuje rekordy do czyszczenia."""
    raw = load_raw_ticket(_write_export(tmp_path))

    assert raw.category == "Automat mailowy"


def test_missing_optional_fields_become_empty(tmp_path: Path):
    """Brakujące pole tekstowe → pusty string, nie None i nie wyjątek."""
    raw = load_raw_ticket(_write_export(tmp_path, czego_dotyczy=None, szczegolowy_opis=None))

    assert raw.subject == ""
    assert raw.body    == ""


def test_null_comments_are_read_as_empty(tmp_path: Path):
    """`komentarze: null` → pusta lista, nie wywrotka; 29 zgłoszeń w korpusie tak wygląda."""
    # Wartość domyślna w `get()` działa tylko przy BRAKU klucza — tu klucz jest, a wartość to null.
    payload = json.loads(_write_export(tmp_path).read_text(encoding="utf-8"))
    payload["komentarze"] = None

    path = tmp_path / "zgloszenie-33644.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    raw = load_raw_ticket(path)

    assert raw.comments == []
    assert "(brak komentarzy w wątku)" in raw.as_thread()


def test_broken_json_is_reported(tmp_path: Path):
    """Uszkodzony plik → ValueError, nie cicho pominięte zgłoszenie."""
    path = tmp_path / "zgloszenie-1.json"
    path.write_text("{nie jestem", encoding="utf-8")

    with pytest.raises(ValueError):
        load_raw_ticket(path)
