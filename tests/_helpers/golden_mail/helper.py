"""
Description:
Golden set kanału „Automat mailowy” (`tickets-mail.json`) i pomiar normalizera maili na nim
(p. 32.3). Wpis to jeden ze 136 wątków: `useful` z 32.1 i pola wątku, każde z autorem wiadomości
i oznaczeniami linii (etykieta na każdą linię ze słowami). Używają go test spójności zestawu
i test ewaluacyjny normalizera.

| funkcja                   | do czego                                                           |
|---------------------------|--------------------------------------------------------------------|
| `golden_mail_tickets()`   | wątki zestawu w kolejności pliku: `useful` i pola z oznaczeniami   |
| `mail_thread()`           | wątek źródłowy z eksportu, czytnikiem eksportu                     |
| `field_digest()`          | skrót tekstu pola, którym oznaczenia pilnują, że opisują ten tekst |
| `parse_ranges()`          | zakresy „1-3 tresc; 4 podpis” na etykietę na linię                 |
| `measure_mail_cleaning()` | przejście normalizera po zestawie: role, słowa, linie po etykiecie |
"""

import hashlib
import json
import re

from app.core_model.tickets.raw_ticket import RawTicket
from app.core_service.loader_mail_dictionary import load_mail_templates, load_vendor_names
from app.core_service.normalizer_ticket_mail import message_texts, normalize_mail_ticket
from app.core_service.parser_ticket_raw import load_raw_ticket
from app.core_util.repetition import repeated_lines, words_of
from tests._helpers.golden_mail.constants import (
    CONTENT_LABEL,
    GOLDEN_FILE,
    LABELS,
    MAIL_DIR,
    RAW_DB_DIR,
    ROLE_OF_AUTHOR,
)
from tests._helpers.golden_mail.models.golden_mail_field import GoldenMailField
from tests._helpers.golden_mail.models.golden_mail_ticket import GoldenMailTicket
from tests._helpers.golden_mail.models.mail_cleaning_measurement import MailCleaningMeasurement
from tests._helpers.golden_mail.models.mail_label_counts import MailLabelCounts

# Jeden zakres oznaczeń: „5 stopka” albo „6-7 kopia”.
RANGE = re.compile(r"^\s*(\d+)(?:\s*-\s*(\d+))?\s+([a-z]+)\s*$")


def golden_mail_tickets() -> list[GoldenMailTicket]:
    """
    Description:
    Czyta wątki golden setu w kolejności pliku: `useful` i pola wątku, każde z autorem, skrótem
    tekstu i etykietą na każdą linię ze słowami.

    Example args:
        (brak)

    Example result:
        [GoldenMailTicket(ticket_id="33315", useful=False, fields=(
            GoldenMailField(author="dostawca", digest="76d7…", labels=("tresc", …)), …)), …]

    Raises:
        ValueError: zakresy któregoś pola są nieczytelne albo mają dziurę
    """
    raw     = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    tickets = [
        GoldenMailTicket(
            ticket_id = entry["ticket_id"],
            useful    = entry["useful"],
            fields    = tuple(
                GoldenMailField(
                    author = field["author"],
                    digest = field["digest"],
                    labels = parse_ranges(field["labels"]),
                )
                for field in entry["fields"]
            ),
        )
        for entry in raw["tickets"]
    ]

    return tickets


def mail_thread(ticket_id: str) -> RawTicket:   # np. "33605"
    """
    Description:
    Czyta wątek źródłowy zgłoszenia z eksportu sierpniowego zrzutu.

    Example args:
        ticket_id="33605"

    Example result:
        RawTicket(ticket_id="33605", category="Automat mailowy", …)
    """
    return load_raw_ticket(RAW_DB_DIR / f"zgloszenie-{ticket_id}.json")


def field_digest(text: str) -> str:   # np. "Dzień dobry,\nod wczoraj nie możemy…"
    """
    Description:
    Liczy skrót tekstu pola (BLAKE2b, 8 bajtów). Oznaczenia linii zapisują go przy każdym polu:
    gdy zmieni się czytnik eksportu albo `message_texts()`, linie mogą się przesunąć, a skrót to
    pokaże, zanim pomiar porówna etykiety z niewłaściwymi liniami.

    Example args:
        text="Dzień dobry,\\nod wczoraj nie możemy wysłać pisma."

    Example result:
        "ad7c2f36723bdde1"
    """
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()


def parse_ranges(spec: str) -> tuple[str, ...]:   # np. "1-2 tresc; 3 podpis; 4-6 kopia"
    """
    Description:
    Zamienia zakresy z pliku oznaczeń na etykietę na linię, w kolejności. Zakresy mają stać po
    kolei od 1, bez dziur i bez nakładania, a etykieta musi być znana.

    Example args:
        spec="1-2 tresc; 3 podpis; 4-6 kopia"

    Example result:
        ("tresc", "tresc", "podpis", "kopia", "kopia", "kopia")

    Raises:
        ValueError: zakres nieczytelny, nie po kolei albo z nieznaną etykietą
    """
    labels: list[str] = []

    for part in filter(str.strip, spec.split(";")):
        match = RANGE.match(part)
        if match is None or match.group(3) not in LABELS:
            raise ValueError(f"nieczytelny zakres oznaczeń: {part.strip()!r}")

        first, last = int(match.group(1)), int(match.group(2) or match.group(1))
        if first != len(labels) + 1 or last < first:
            raise ValueError(f"zakres {first}-{last} nie stoi tuż za linią {len(labels)}")

        labels += [match.group(3)] * (last - first + 1)

    return tuple(labels)


def measure_mail_cleaning() -> MailCleaningMeasurement:
    """
    Description:
    Przepuszcza normalizer maili przez 136 wątków golden setu ze słownikiem instancji i liczy:
    ile ról zgadza się z autorami z 32.1, ile słów zostaje oraz ile linii każdej etykiety zostało,
    a ile zniknęło. Które linie zniknęły, mówi `repeated_lines()`, a pomiar sprawdza przy każdym
    polu, że normalizer oddał dokładnie słowa linii, które zostały; pole, w którym się to nie
    zgadza, trafia na listę `mismatched`.

    Example args:
        (brak)

    Example result:
        MailCleaningMeasurement(role_fields=367, role_matches=353, words_before=93449, …)
    """
    templates = load_mail_templates(MAIL_DIR)
    vendors   = load_vendor_names(MAIL_DIR)
    known     = frozenset(templates.digests)

    by_label:     dict[str, MailLabelCounts] = {label: MailLabelCounts() for label in LABELS}
    role_fields:  int                        = 0
    role_matches: int                        = 0
    words_before: int                        = 0
    words_after:  int                        = 0
    lost_useful:  int                        = 0
    lost_fields:  list[str]                  = []
    mismatched:   list[str]                  = []

    for ticket in golden_mail_tickets():
        raw        = mail_thread(ticket.ticket_id)
        normalized = normalize_mail_ticket(raw, templates, vendors)
        roles      = [normalized.body_role, *(comment.role for comment in normalized.comments)]
        after      = [normalized.body, *(comment.body for comment in normalized.comments)]
        texts      = message_texts(raw)
        removed    = repeated_lines(texts, templates.run_words, known)

        # --- role: pole puste („brak”) się pomija, „system” roli nie ma ---
        for role, field in zip(roles, ticket.fields, strict=True):
            if field.author == "brak":
                continue
            role_fields  += 1
            role_matches += int(ROLE_OF_AUTHOR.get(field.author) == role)

        # --- linie: etykieta wobec tego, czy linia została ---
        fields = zip(texts, removed, after, ticket.fields, strict=True)
        for index, (text, flags, cleaned, field) in enumerate(fields):
            place      = f"{ticket.ticket_id}:{index}"
            word_lines = [
                (line, gone)
                for line, gone in zip(text.split("\n"), flags, strict=True)
                if words_of(line)
            ]
            kept_words = [word for line, gone in word_lines if not gone for word in words_of(line)]

            if kept_words != words_of(cleaned):
                mismatched.append(place)

            words_before += sum(len(words_of(line)) for line, _ in word_lines)
            words_after  += len(kept_words)

            for (line, gone), label in zip(word_lines, field.labels, strict=True):
                counts = by_label[label]
                count  = len(words_of(line))
                if gone:
                    counts.removed_lines += 1
                    counts.removed_words += count
                else:
                    counts.kept_lines += 1
                    counts.kept_words += count

            lost = sum(
                gone and label == CONTENT_LABEL
                for (_, gone), label in zip(word_lines, field.labels, strict=True)
            )
            if lost:
                lost_fields.append(place)
                lost_useful += lost if ticket.useful else 0

    measurement = MailCleaningMeasurement(
        role_fields    = role_fields,
        role_matches   = role_matches,
        words_before   = words_before,
        words_after    = words_after,
        by_label       = by_label,
        lost_in_useful = lost_useful,
        lost_fields    = tuple(lost_fields),
        mismatched     = tuple(mismatched),
    )

    return measurement
