"""
Description:
Golden set kanału „Automat mailowy” z `data/unsafe/golden/service-tickets-mail.json`: etykiety
wątków z 32.1 i autor oraz oznaczenia linii każdego pola z 32.3, a także pomiar normalizera maili na
nich. Używają go test spójności zestawu i test ewaluacyjny normalizera.

Logika leży w `helper.py`, stałe w `constants.py`, modele w `models/`; testy importują je
z pakietu.
"""

from tests._helpers.golden_mail.constants import (
    CONTENT_LABEL,
    GOLDEN_FILE,
    JUNK_LABELS,
    LABELS,
    MAIL_DIR,
    MAX_JUNK_SHARE,
    MAX_KEPT_WORD_SHARE,
    MAX_LOST_CONTENT_SHARE,
    MAX_LOST_LINES_IN_USEFUL,
    MIN_ROLE_SHARE,
    RAW_DB_DIR,
    ROLE_OF_AUTHOR,
)
from tests._helpers.golden_mail.helper import (
    field_digest,
    golden_mail_tickets,
    mail_thread,
    measure_mail_cleaning,
    parse_ranges,
)
from tests._helpers.golden_mail.models.golden_mail_field import GoldenMailField
from tests._helpers.golden_mail.models.golden_mail_ticket import GoldenMailTicket
from tests._helpers.golden_mail.models.mail_cleaning_measurement import MailCleaningMeasurement
from tests._helpers.golden_mail.models.mail_label_counts import MailLabelCounts

__all__ = [
    "CONTENT_LABEL",
    "GOLDEN_FILE",
    "JUNK_LABELS",
    "LABELS",
    "MAIL_DIR",
    "MAX_JUNK_SHARE",
    "MAX_KEPT_WORD_SHARE",
    "MAX_LOST_CONTENT_SHARE",
    "MAX_LOST_LINES_IN_USEFUL",
    "MIN_ROLE_SHARE",
    "RAW_DB_DIR",
    "ROLE_OF_AUTHOR",
    "GoldenMailField",
    "GoldenMailTicket",
    "MailCleaningMeasurement",
    "MailLabelCounts",
    "field_digest",
    "golden_mail_tickets",
    "mail_thread",
    "measure_mail_cleaning",
    "parse_ranges",
]
