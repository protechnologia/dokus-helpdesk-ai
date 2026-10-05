import json
from pathlib import Path

import pytest

from app.core_service.validator_ticket_parsed import validate_directory, validate_file

VALID_TICKET = {
    "ticket_id":                     "33644",
    "date":                          "2026-03-14",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka kończy się błędem komunikacji",
    "symptoms":                      "Komunikat o braku połączenia po kliknięciu Wyślij",
    "error_codes":                   ["ERR-4210"],
    "cause":                         "brak",
    "solution":                      "brak",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "brak",
}


def _write(directory: Path, name: str, payload: dict | str) -> Path:
    """
    Description:
    Writes an artifact file, accepting either a dict to serialise or raw text — raw text is how a
    malformed file is produced, which no dict could express.

    Example args:
        directory=Path("/tmp/x")
        name="33644.json"
        payload={"ticket_id": "33644", …}

    Example result:
        Path("/tmp/x/33644.json")
    """
    path = directory / name
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")

    return path


def test_valid_file_passes(tmp_path: Path) -> None:
    """Sprawdza, czy plik zgodny z kontraktem sparsowanego zgłoszenia przechodzi walidację:
    werdykt jest pozytywny i nie ma w nim żadnego błędu.

    Wyłapuje walidator, który zgłasza błędy w poprawnym pliku — raport z całego korpusu byłby
    wtedy pełen fałszywych alarmów."""
    verdict = validate_file(_write(tmp_path, "ok.json", VALID_TICKET))

    assert verdict.ok
    assert verdict.errors == []


def test_unknown_field_is_reported(tmp_path: Path) -> None:
    """Sprawdza, czy klucz, którego kontrakt nie przewiduje (tu `severity`), daje błąd z nazwą
    tego klucza.

    Wyłapuje ciche kasowanie nadmiarowych pól: model parsujący zgłoszenia potrafi dołożyć własne
    pole, a jego przebieg jest jednorazowy, więc treści skasowanej bez śladu nie da się
    odzyskać."""
    verdict = validate_file(_write(tmp_path, "extra.json", {**VALID_TICKET, "severity": "wysoka"}))

    assert not verdict.ok
    assert any("severity" in error for error in verdict.errors)


def test_resolution_outside_vocabulary_is_reported(tmp_path: Path) -> None:
    """Sprawdza, czy rodzaj rozstrzygnięcia spoza słownika (tu `zamkniete-bo-tak`) daje błąd,
    który wymienia wartości dozwolone — test szuka w nim wartości `naprawione`.

    Wyłapuje plik przyjęty mimo wartości spoza słownika oraz komunikat, który mówi tylko, że
    wartość jest zła, i zostawia człowieka bez wiedzy, co wolno wpisać."""
    broken = {**VALID_TICKET, "resolution": "zamkniete-bo-tak"}

    verdict = validate_file(_write(tmp_path, "res.json", broken))

    assert not verdict.ok
    # The message must list what IS allowed; "invalid value" alone leaves the operator guessing.
    assert any("naprawione" in error for error in verdict.errors)


def test_foreign_vocabulary_version_is_reported(tmp_path: Path) -> None:
    """Sprawdza, czy rekord zapisany z inną wersją słownika rozstrzygnięć, niż ma ta instalacja
    (tu wersja 99), daje błąd, który podaje tę wersję.

    Wyłapuje rekord z obcej wersji słownika oceniony dzisiejszym słownikiem oraz komunikat bez
    numeru wersji: po zmianie słownika nie byłoby widać, że wszystkie takie błędy mają jedną
    przyczynę."""
    broken = {**VALID_TICKET, "resolution_vocabulary_version": 99}

    verdict = validate_file(_write(tmp_path, "ver.json", broken))

    assert not verdict.ok
    assert any("99" in error for error in verdict.errors)


def test_malformed_json_is_reported_not_raised(tmp_path: Path) -> None:
    """Sprawdza, czy plik z urwanym JSON-em daje werdykt z błędem, a nie wyjątek.

    Wyłapuje wyjątek, który przez jeden nieczytelny plik przerwałby sprawdzanie całego korpusu —
    a ten przebieg robi się po to, żeby zobaczyć wszystkie problemy naraz."""
    verdict = validate_file(_write(tmp_path, "broken.json", '{ "ticket_id": '))

    assert not verdict.ok
    assert verdict.errors


def test_every_error_line_names_a_location(tmp_path: Path) -> None:
    """Sprawdza, czy każda linia błędu wskazuje miejsce, którego dotyczy — nazwę pola albo słowo
    `rekord` — oddzielone dwukropkiem od opisu; test patrzy, czy w każdej linii jest dwukropek.

    Wyłapuje błąd podany bez wskazania pola: przy setkach linii z całego korpusu taki raport nie
    mówi, co poprawić."""
    verdict = validate_file(_write(tmp_path, "extra.json", {**VALID_TICKET, "severity": "x"}))

    assert all(":" in error for error in verdict.errors)


def test_directory_report_separates_valid_from_broken(tmp_path: Path) -> None:
    """Sprawdza, czy w katalogu z dwoma poprawnymi plikami i jednym błędnym każdy plik dostaje
    werdykt, raport jest negatywny, a lista plików z błędami zawiera tylko ten jeden błędny.

    Wyłapuje raport, który gubi pliki albo miesza poprawne z błędnymi: nie dałoby się wtedy
    z niego odczytać, które pliki trzeba poprawić."""
    _write(tmp_path, "a_ok.json", VALID_TICKET)
    _write(tmp_path, "b_bad.json", {**VALID_TICKET, "resolution": "nieznane"})
    _write(tmp_path, "c_ok.json", {**VALID_TICKET, "ticket_id": "999"})

    report = validate_directory(tmp_path)

    assert len(report.verdicts) == 3
    assert not report.ok
    assert [verdict.path.name for verdict in report.failed] == ["b_bad.json"]


def test_files_are_reported_in_stable_order(tmp_path: Path) -> None:
    """Sprawdza, czy werdykty wracają w kolejności nazw plików: pliki zapisane w kolejności
    `c.json`, `a.json`, `b.json` są w raporcie jako `a.json`, `b.json`, `c.json`.

    Wyłapuje kolejność zależną od systemu plików: dwa przebiegi po tym samym korpusie dawałyby
    wtedy raporty, których nie da się porównać."""
    for name in ("c.json", "a.json", "b.json"):
        _write(tmp_path, name, VALID_TICKET)

    names = [verdict.path.name for verdict in validate_directory(tmp_path).verdicts]

    assert names == ["a.json", "b.json", "c.json"]


def test_empty_directory_passes(tmp_path: Path) -> None:
    """Sprawdza, czy pusty katalog daje pusty, pozytywny raport: bez werdyktów i bez błędów.

    Wyłapuje walidator, który brak plików uznaje za błąd: katalog bez sparsowanych zgłoszeń to
    zwykły stan świeżej instalacji, a nie usterka."""
    report = validate_directory(tmp_path)

    assert report.ok
    assert report.verdicts == []


def test_non_json_files_are_ignored(tmp_path: Path) -> None:
    """Sprawdza, czy walidator patrzy tylko na pliki `*.json`: w katalogu z jednym poprawnym
    plikiem zgłoszenia i z plikiem `notatki.md` raport ma jeden werdykt.

    Wyłapuje walidator, który notatki albo README czyta jak sparsowane zgłoszenie i zgłasza
    w nich błędy, których nie ma."""
    _write(tmp_path, "ok.json", VALID_TICKET)
    (tmp_path / "notatki.md").write_text("nie artefakt", encoding="utf-8")

    assert len(validate_directory(tmp_path).verdicts) == 1


def test_missing_directory_raises(tmp_path: Path) -> None:
    """Sprawdza, czy ścieżka, pod którą nie ma katalogu, kończy się wyjątkiem
    `NotADirectoryError`.

    Wyłapuje pomylenie złej ścieżki z wynikiem walidacji: literówka w ścieżce nie może wyglądać
    ani jak pusty, pozytywny raport, ani jak błędne pliki zgłoszeń."""
    with pytest.raises(NotADirectoryError):
        validate_directory(tmp_path / "nie-ma")
