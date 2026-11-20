import dataclasses

from tests._helpers.golden_mail.models.mail_label_counts import MailLabelCounts


@dataclasses.dataclass(frozen=True)
class MailCleaningMeasurement:
    """Przejście normalizera maili po 136 wątkach golden setu: role wobec etykiet z 32.1 i linie
    wobec oznaczeń linii."""

    role_fields:    int                         # pola z autorem w etykiecie (bez pól pustych)
    role_matches:   int                         # z nich pola, w których rola z reguły się zgadza
    words_before:   int                         # słowa wszystkich pól przed czyszczeniem
    words_after:    int                         # słowa, które zostały
    by_label:       dict[str, MailLabelCounts]  # etykieta → co zostało, co zniknęło
    lost_in_useful: int                         # linie `tresc` usunięte w wątkach z wiedzą
    lost_fields:    tuple[str, ...]             # „numer:pole” pól z usuniętą linią `tresc`
    mismatched:     tuple[str, ...]             # „numer:pole”, gdzie normalizer oddał co innego
