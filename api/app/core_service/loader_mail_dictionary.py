"""
Description:
Czyta słownik maili, którym normalizer czyści wątki kanału „Automat mailowy” (p. 32): dwa pliki
z jednego katalogu. Słownik instancji leży w `data/unsafe/mail/`, bo powstaje z maili klienta,
a zmyślony, do testów, w `data/safe/mail/`.

| plik           | kto go pisze                                          | model           |
|----------------|-------------------------------------------------------|-----------------|
| `slownik.json` | skrypt `scripts/build_mail_dictionary.py`, z korpusu  | `MailTemplates` |
| `nazwy.json`   | człowiek, ręcznie                                     | `VendorNames`   |

Przed — katalog słownika zmyślonego:

    slownik.json  {"built_on": "2026-11-20", "threads": 3, "run_words": 12, "digests": […], …}
    nazwy.json    {"names": ["Przykładsoft Sp. z o.o."]}

Po:

    load_mail_templates(katalog)  →  MailTemplates(threads=3, run_words=12, digests=[…], …)
    load_vendor_names(katalog)    →  VendorNames(names=["Przykładsoft Sp. z o.o."])

O czym pamiętać przy zmianach:

- Dwa pliki, bo mają dwa rytmy zmian: skrypt buduje słownik od nowa przy każdym przebiegu,
  a nazwy wpisuje człowiek, więc przebudowa nie może ich ruszyć.
- Brak pliku albo plik w złym kształcie to `MailDictionaryConfigError`, błąd wdrożenia: nie
  zamienia się w pusty słownik. Wątek mailowy przepuszczony bez czyszczenia szedłby do
  anonimizatora kilka razy dłuższy, z nazwiskami i adresami ze stopek i cytatów, a nikt by
  tego nie zauważył.
- Pliki czyta się przy każdym wywołaniu, bez pamiętania; kiedy je czytać, decyduje wołający.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from app.core_model.dicts.mail_templates import MailTemplates
from app.core_model.dicts.vendor_names import VendorNames

# Słownik szablonów: buduje go skrypt słownika maili.
TEMPLATES_FILE = "slownik.json"

# Nazwy dostawcy z podpisów: pisze je człowiek.
NAMES_FILE = "nazwy.json"


class MailDictionaryConfigError(Exception):
    """
    Description:
    Słownika maili nie ma tam, gdzie wskazuje wołający, albo któryś z jego plików jest nie do
    odczytania. Błąd wdrożenia, a nie wywołania: zatrzymuje przebieg, zamiast przepuścić wątek
    mailowy bez czyszczenia.
    """


def load_mail_templates(directory: Path) -> MailTemplates:   # np. Path("/code/data/unsafe/mail")
    """
    Description:
    Czyta słownik szablonów (`slownik.json`) z katalogu słownika maili.

    Example args:
        directory=Path("/code/data/unsafe/mail")

    Example result:
        MailTemplates(built_on=date(2026, 11, 20), threads=139, run_words=12, digests=[…], …)

    Raises:
        MailDictionaryConfigError: pliku nie ma albo nie ma kształtu słownika szablonów
    """
    path = directory / TEMPLATES_FILE
    hint = "zbuduj go skryptem słownika (scripts/build_mail_dictionary.py)"

    try:
        templates = MailTemplates.model_validate(_read_json(path, hint))
    except ValidationError as exc:
        raise MailDictionaryConfigError(_unreadable(path, hint)) from exc

    return templates


def load_vendor_names(directory: Path) -> VendorNames:   # np. Path("/code/data/unsafe/mail")
    """
    Description:
    Czyta nazwy dostawcy (`nazwy.json`) z katalogu słownika maili.

    Example args:
        directory=Path("/code/data/unsafe/mail")

    Example result:
        VendorNames(names=["TENSOFT Sp. z o.o."])

    Raises:
        MailDictionaryConfigError: pliku nie ma albo nie ma kształtu listy nazw
    """
    path = directory / NAMES_FILE
    hint = 'plik pisze się ręcznie: {"names": ["<nazwa firmy z formą prawną>"]}'

    try:
        names = VendorNames.model_validate(_read_json(path, hint))
    except ValidationError as exc:
        raise MailDictionaryConfigError(_unreadable(path, hint)) from exc

    return names


def _read_json(
    path: Path,  # np. Path("/code/data/unsafe/mail/slownik.json")
    hint: str,   # np. "zbuduj go skryptem słownika (scripts/build_mail_dictionary.py)"
) -> object:
    """
    Description:
    Czyta plik JSON; brak pliku, inne kodowanie i zły JSON zamienia na błąd konfiguracji
    z nazwą pliku i podpowiedzią, skąd wziąć poprawny.

    Example args:
        path=Path("/code/data/unsafe/mail/slownik.json")
        hint="zbuduj go skryptem słownika (scripts/build_mail_dictionary.py)"

    Example result:
        {"built_on": "2026-11-20", "threads": 139, …}

    Raises:
        MailDictionaryConfigError: pliku nie ma, nie jest w UTF-8 albo nie jest JSON-em
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (
        OSError,               # pliku nie ma albo nie da się go otworzyć
        UnicodeDecodeError,    # plik w innym kodowaniu niż UTF-8
        json.JSONDecodeError,  # plik nie jest JSON-em
    ) as exc:
        raise MailDictionaryConfigError(_unreadable(path, hint)) from exc

    return raw


def _unreadable(
    path: Path,  # np. Path("/code/data/unsafe/mail/nazwy.json")
    hint: str,   # np. "plik pisze się ręcznie: …"
) -> str:
    """
    Description:
    Składa komunikat błędu konfiguracji: który plik i skąd wziąć poprawny. Treści pliku nie
    cytuje.

    Example args:
        path=Path("/code/data/unsafe/mail/nazwy.json")
        hint='plik pisze się ręcznie: {"names": ["<nazwa firmy z formą prawną>"]}'

    Example result:
        "słownik maili jest nie do odczytania: /code/data/unsafe/mail/nazwy.json — plik pisze…"
    """
    return f"słownik maili jest nie do odczytania: {path} — {hint}"
