"""
Description:
Słownik maili zmyślony z `data/safe/mail/` i zgłoszenia z kanału „Automat mailowy” do testów
normalizera maili, jego loadera i skryptu słownika.

Logika leży w `helper.py`, stałe w `constants.py`; testy importują je z pakietu. Zmyślone maile,
na których stoją asercje, leżą w `samples.py` i test bierze je z modułu.
"""

from tests._helpers.mail.constants import BUILD_COMMAND, REPO_ROOT, SAFE_MAIL_DIR, VENDOR_NAME
from tests._helpers.mail.helper import (
    copy_safe_mail_export,
    mail_ticket,
    safe_mail_request,
    safe_mail_ticket,
    safe_templates,
    safe_vendor_names,
)

__all__ = [
    "BUILD_COMMAND",
    "REPO_ROOT",
    "SAFE_MAIL_DIR",
    "VENDOR_NAME",
    "copy_safe_mail_export",
    "mail_ticket",
    "safe_mail_request",
    "safe_mail_ticket",
    "safe_templates",
    "safe_vendor_names",
]
