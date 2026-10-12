from pathlib import Path

from app.core_util.markdown import read_document


def test_editorial_comments_do_not_reach_the_reader(tmp_path: Path) -> None:
    """Sprawdza, czy z dokumentu znikają komentarze redakcyjne, także wieloliniowe i ze środka
    tekstu, razem z odstępem po nich, a reszta treści zostaje bez zmian.

    Wyłapuje odczyt, który zostawia notatkę pisaną dla nas: trafiłaby do modelu jako część
    promptu, opisu narzędzia albo opisu projektu."""
    document = tmp_path / "prompt.md"
    document.write_text(
        "<!-- notatka\n     na dwie linie -->\nJesteś asystentem.\n<!-- druga -->\nKoniec.\n",
        encoding="utf-8",
    )

    assert read_document(document) == "Jesteś asystentem.\nKoniec.\n"


def test_a_document_changed_on_disk_is_read_again(tmp_path: Path) -> None:
    """Sprawdza, czy drugi odczyt tego samego pliku po jego zmianie oddaje nową treść.

    Wyłapuje odczyt, który pamięta plik od pierwszego wywołania: opis projektu w paczce kodu
    poprawia się bez restartu usługi, więc model dostawałby starą wersję."""
    document = tmp_path / "project.md"

    document.write_text("Pierwsza wersja.", encoding="utf-8")
    first = read_document(document)

    document.write_text("Druga wersja.", encoding="utf-8")

    assert (first, read_document(document)) == ("Pierwsza wersja.", "Druga wersja.")
