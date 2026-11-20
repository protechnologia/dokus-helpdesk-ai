"""
Description:
Buduje z konfiguracji czyszczenie wątków kanału „Automat mailowy” (`MailNormalizer`, p. 32) dla
tras grafów: katalog słownika maili bierze z `TICKETS_MAIL_DIR`. Masowy import dostaje
normalizer od swojej fabryki (`factory_tickets_importer.py`), z tej samej konfiguracji.

Do czego:
Trasy `/search`, `/gate/close`, `/parse-ticket`, `/suggest` i `/tickets/closed` biorą
normalizer zależnością FastAPI (`get_mail_normalizer()`), tak jak graf z fabryki grafów, więc
test może go podmienić.

O czym pamiętać przy zmianach:

- Normalizer nie trzyma połączeń ani słownika, więc powstaje raz na proces tylko po to, żeby
  nie czytać konfiguracji przy każdym żądaniu; słownik czyta przy każdym zgłoszeniu mailowym.
"""

import functools

from app.config import Settings
from app.core_service.normalizer_ticket_mail import MailNormalizer


@functools.cache
def process_mail_normalizer() -> MailNormalizer:
    """
    Description:
    Normalizer zbudowany raz na proces, na katalogu słownika maili z konfiguracji.

    Example args:
        (brak)

    Example result:
        MailNormalizer czytający /code/data/unsafe/mail
    """
    return MailNormalizer(Settings().tickets_mail_dir)


def get_mail_normalizer() -> MailNormalizer:
    """
    Description:
    Zależność FastAPI: skąd trasy grafów biorą czyszczenie wątków mailowych. Osobna od
    `process_mail_normalizer()`, żeby test mógł ją podmienić (`app.dependency_overrides`).

    Example args:
        (brak)

    Example result:
        MailNormalizer zbudowany raz na proces
    """
    return process_mail_normalizer()
