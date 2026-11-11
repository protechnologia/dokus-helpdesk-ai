from pathlib import Path

import pytest

from app.config import Settings

# Katalog korpusu zgłoszeń w konfiguracji: jedna zmienna na katalog główny, z którego komendy
# `helpdesk tickets` i trasa zamknięcia zgłoszenia biorą podkatalogi.


def test_the_corpus_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy katalog korpusu da się ustawić zmienną środowiskową: przy
    `TICKETS_CORPUS_DIR=/dane/korpus` karty leżą w `/dane/korpus/cards`.

    Wyłapuje katalog zaszyty w kodzie albo czytany spod innej nazwy: wdrożenie z korpusem w innym
    miejscu indeksowałoby wtedy z katalogu, którego nie ma."""
    monkeypatch.setenv("TICKETS_CORPUS_DIR", "/dane/korpus")

    corpus = Settings(_env_file=None).tickets_corpus()

    assert corpus.cards_dir == Path("/dane/korpus/cards")


def test_the_default_corpus_is_the_container_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy bez zmiennej katalogiem korpusu jest `/code/data/unsafe/corpus`, czyli
    miejsce, pod którym compose montuje `./data` w kontenerze `api`.

    Wyłapuje domyślną ścieżkę, która rozjechała się z montowaniem: komenda uruchomiona w kontenerze
    bez argumentu szukałaby kart poza zamontowanym katalogiem."""
    monkeypatch.delenv("TICKETS_CORPUS_DIR", raising=False)

    corpus = Settings(_env_file=None).tickets_corpus()

    assert corpus.root == Path("/code/data/unsafe/corpus")
