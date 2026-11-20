"""
Description:
Czyści wątek zgłoszenia z kanału „Automat mailowy”, zanim trafi do anonimizatora i do modelu
(p. 32). W tym kanale zgłoszeniem jest mail zapisany wprost do bazy, więc treść to kilka
procent tekstu, a resztę zajmują druga kopia tego samego maila (HTML i zwykły tekst), cytowana
historia korespondencji i stopki. Do tego role z bazy są błędne: system zapisuje nadawcę
maila, a nie autora wypowiedzi. Zgłoszenie z każdego innego kanału wraca bez zmian.

Przed — wątek z dwóch maili, w kształcie `RawTicket.as_thread()`, ze słownikiem zmyślonym
z `data/safe/mail/`:

    OPIS ZGŁASZAJĄCEGO:
    Dzień dobry,
    od wczoraj nie możemy wysłać żadnego pisma do ePUAP.
    Jan Kowalski
    Dzień dobry, od wczoraj nie możemy wysłać żadnego
    pisma do ePUAP. Jan Kowalski

    KOMENTARZ 1 — klient, 2026-07-03 10:00:00 (typ: zwyczajny):
    Proszę ponownie nadać uprawnienie do skrzynki ePUAP.
    Anna Nowak | Przykładsoft Sp. z o.o. [cid:image001.png@01DCF2C1]
    Ta wiadomość i jej załączniki są poufne i przeznaczone wyłącznie dla wskazanego odbiorcy.
    Od: Jan Kowalski
    > Dzień dobry,
    > od wczoraj nie możemy wysłać żadnego pisma do ePUAP.
    > Jan Kowalski

Po:

    OPIS ZGŁASZAJĄCEGO — klient:
    Dzień dobry,
    od wczoraj nie możemy wysłać żadnego pisma do ePUAP.
    Jan Kowalski

    KOMENTARZ 1 — konsultant, 2026-07-03 10:00:00 (typ: zwyczajny):
    Proszę ponownie nadać uprawnienie do skrzynki ePUAP.
    Anna Nowak | Przykładsoft Sp. z o.o.
    Od: Jan Kowalski

Co się zmieniło:

1. Autor każdej wiadomości jest ustalony z podpisu, zanim czyszczenie zdejmie stopki: dostawca
   (rola `konsultant`), gdy w jej własnej części, przed cytatem, stoi nazwa dostawcy
   z `nazwy.json`, a w każdym innym przypadku klient. Rola `konsultant` z bazy zostaje, bo
   system zapisuje ją tylko przy odpowiedzi konsultanta z helpdesku. Autor opisu idzie do
   `body_role`, więc nagłówek opisu go pokazuje.
2. Znikają odwołania do obrazków w treści (`[cid:image001.png@…]`).
3. Znikają linie powtórzone: każde słowo linii leży w ciągu co najmniej 12 słów, który stał już
   wcześniej w wątku, także w tym samym polu (druga kopia maila).
4. Znikają linie szablonów: fragmentów, które stoją w co najmniej 10 różnych wątkach kanału
   (`slownik.json`), także przy pierwszym wystąpieniu.

Trasy grafów i masowy import wołają `MailNormalizer`, który czyta słownik maili z katalogu
z konfiguracji (`TICKETS_MAIL_DIR`) i oddaje zgłoszenie spoza kanału bez zmian, nie dotykając
dysku; `normalize_mail_ticket()` zostaje czystą funkcją na podanym słowniku.

O czym pamiętać przy zmianach:

- Tekst po czyszczeniu nigdzie się nie zapisuje: liczy się w locie ze źródła, jak `as_thread()`,
  więc lepsza reguła działa od razu na całym korpusie, bez przebiegu po plikach. Surowe
  zgłoszenie z trasy zamknięcia trafia do `raw-route/` bez czyszczenia, a oczyszczony wątek
  idzie do grafów i, po anonimizacji, do `anonymized/`.
- Słownik szablonów musi powstać z tekstów w tym samym kształcie, który czyści normalizer:
  dlatego skrypt słownika bierze je z `message_texts()`, a nie składa sam.
- Znika cała linia albo nic: strzępy zdań model czyta gorzej niż linię, która została.
  Znany koszt: odpowiedź wpleciona w cytat, między jego linie, zostaje razem z sąsiednimi
  liniami cytatu (w 136 wątkach takich było 4, wszystkie bez wiedzy).
- Sprawy rozbitej na dwa zgłoszenia (prośba i odpowiedź osobno) nie skleja się: późniejsze
  zgłoszenie cytuje prośbę, więc czyszczenie wątku jej nie gubi.
"""

import re
from pathlib import Path

from app.core_model.dicts.mail_templates import MailTemplates
from app.core_model.dicts.vendor_names import VendorNames
from app.core_model.tickets.raw_comment import RawComment
from app.core_model.tickets.raw_ticket import RawTicket
from app.core_service.loader_mail_dictionary import load_mail_templates, load_vendor_names
from app.core_service.parser_ticket_raw import MAIL_CATEGORY
from app.core_util.repetition import WORD, remove_repeated_lines, words_of

# Role w słownictwie źródła (`autor_rola` eksportu) — te same, które podpisuje `as_thread()`.
VENDOR_ROLE = "konsultant"
CLIENT_ROLE = "klient"

# Odwołanie do obrazka wklejonego w mail: „[cid:image001.png@01DAF2C1.5B3E9A40]”, razem
# z odstępem przed nim. Identyfikator jest inny w każdej kopii maila, więc zostawiony rozbijałby
# powtórzenia linii, w których stoi.
IMAGE_REFERENCE = re.compile(r"[ \t]*\[?cid:[^\s\]]+\]?")

# Od ilu słów własnej treści nagłówek cytatu kończy własną część wiadomości. Krótsza treść
# („FYI”, „Przesyłam dalej”) to przekazanie, po którym autora mówi podpis przekazanej
# wiadomości: na 136 wątkach próg 3 dał 96,2% ról zgodnych z etykietami, a 1 słowo — 95,6%.
MIN_OWN_WORDS = 3

# Linia nagłówka cytowanej wiadomości: od niej zaczyna się cytat pod własną treścią maila.
QUOTE_HEADER = re.compile(
    r"[ \t>]*(?:"
    # pole nagłówka: „Od: …”, „Wysłano: …”, „Subject: …”
    r"(?:Od|From|Wysłano|Wysłane|Sent|Do|To|DW|Cc|UDW|Temat|Subject|Data|Date|Priorytet"
    r"|Importance)\s*:.*"
    # wstęp cytatu w treści: „W dniu 3 lipca 2026 Jan Kowalski napisał(a):”
    r"|.*(?:napisał\(a\)|napisała|napisał|wrote)\s*:\s*"
    # separator programu pocztowego: „-----Original Message-----”
    r"|-{2,}\s*(?:Original Message|Wiadomość oryginalna|Oryginalna wiadomość|Forwarded message"
    r"|Wiadomość przekazana)\s*-*\s*"
    # linia podkreśleń, którą Outlook stawia nad cytatem
    r"|_{10,}\s*"
    r")",
    re.IGNORECASE,
)


class MailNormalizer:
    """
    Description:
    Czyszczenie wątków kanału „Automat mailowy” ze słownikiem maili z jednego katalogu: to,
    czego używają trasy grafów i masowy import przed zrobieniem tekstu wątku.

    Do czego:
    Spina `normalize_mail_ticket()` ze słownikiem z dysku. Słownik czyta tylko przy zgłoszeniu
    z kanału, więc instancja bez słownika obsługuje pozostałe kanały, a brak słownika wychodzi
    przy pierwszym zgłoszeniu mailowym jako błąd konfiguracji. Pliki czyta przy każdym takim
    zgłoszeniu, bez pamiętania: to dwa małe pliki, a przebudowany słownik działa bez restartu.

    Flow:
        1. Konstruktor zapamiętuje katalog słownika; dysku nie dotyka.
        2. `normalize()` oddaje zgłoszenie spoza kanału bez zmian, a mailowe czyści
           `normalize_mail_ticket()` ze słownikiem i nazwami dostawcy przeczytanymi z katalogu.
    """

    def __init__(
        self,
        directory: Path,  # np. Path("/code/data/unsafe/mail")
    ):
        """
        Description:
        Zapamiętuje katalog słownika maili. Nie sprawdza, czy pliki istnieją: brak słownika
        wychodzi przy pierwszym zgłoszeniu z kanału.

        Example args:
            directory=Path("/code/data/unsafe/mail")

        Example result:
            MailNormalizer czytający /code/data/unsafe/mail/slownik.json i nazwy.json
        """
        self._directory = directory

    def normalize(self, raw: RawTicket) -> RawTicket:   # np. RawTicket(ticket_id="41101", …)
        """
        Description:
        Oddaje zgłoszenie z kanału „Automat mailowy” oczyszczone, z autorami z podpisów, a każde
        inne bez zmian i bez czytania słownika.

        Example args:
            raw=RawTicket(ticket_id="41101", category="Automat mailowy", …)

        Example result:
            RawTicket(ticket_id="41101", body_role="klient", body="Dzień dobry,…", …)

        Raises:
            MailDictionaryConfigError: zgłoszenie jest z kanału, a słownika maili nie ma albo jest
                nie do odczytania
        """
        if raw.category != MAIL_CATEGORY:
            return raw

        templates = load_mail_templates(self._directory)
        vendors   = load_vendor_names(self._directory)

        return normalize_mail_ticket(raw, templates, vendors)


def normalize_mail_ticket(
    raw:       RawTicket,      # np. RawTicket(ticket_id="41101", category="Automat mailowy", …)
    templates: MailTemplates,  # np. MailTemplates(run_words=12, digests=[…], …)
    vendors:   VendorNames,    # np. VendorNames(names=["TENSOFT Sp. z o.o."])
) -> RawTicket:
    """
    Description:
    Oddaje zgłoszenie z kanału „Automat mailowy” z ustalonymi autorami wiadomości i bez
    odwołań do obrazków, linii powtórzonych i linii szablonów. Zgłoszenie z innego kanału
    oddaje bez zmian.

    Example args:
        raw=RawTicket(ticket_id="41101", category="Automat mailowy", body="Dzień dobry,…", …)
        templates=MailTemplates(run_words=12, digests=["0d3c…", …], …)
        vendors=VendorNames(names=["Przykładsoft Sp. z o.o."])

    Example result:
        RawTicket(ticket_id="41101", body="Dzień dobry,…", body_role="klient",
                  comments=[RawComment(role="konsultant", body="Dzień dobry, po aktualizacji…")])
    """
    if raw.category != MAIL_CATEGORY:
        return raw

    # --- autorzy: z tekstu przed czyszczeniem, bo czyszczenie zdejmuje stopki z nazwą firmy ---
    texts       = message_texts(raw)
    body_role   = message_author(texts[0], "", vendors)
    roles       = [
        message_author(text, comment.role, vendors)
        for text, comment in zip(texts[1:], raw.comments, strict=True)
    ]

    # --- czyszczenie całego wątku naraz: cytat w komentarzu powtarza wcześniejsze pola ---
    cleaned = remove_repeated_lines(texts, templates.run_words, frozenset(templates.digests))

    normalized = RawTicket(
        ticket_id = raw.ticket_id,
        date      = raw.date,
        category  = raw.category,
        subject   = raw.subject,
        body      = cleaned[0],
        body_role = body_role,
        comments  = [
            RawComment(kind=comment.kind, role=role, created_at=comment.created_at, body=body)
            for comment, role, body in zip(raw.comments, roles, cleaned[1:], strict=True)
        ],
    )

    return normalized


def message_texts(raw: RawTicket) -> list[str]:   # np. RawTicket(ticket_id="41101", …)
    """
    Description:
    Oddaje treść każdej wiadomości wątku, opis i po nim komentarze, bez odwołań do obrazków:
    w tym kształcie normalizer szuka powtórzeń, a skrypt słownika liczy szablony.

    Example args:
        raw=RawTicket(body="Pozdrawiam [cid:image001.png@01DA]\\nJan", comments=[…])

    Example result:
        ["Pozdrawiam \\nJan", "Dzień dobry, po aktualizacji…"]
    """
    bodies = [raw.body, *(comment.body for comment in raw.comments)]
    texts  = [IMAGE_REFERENCE.sub("", body) for body in bodies]

    return texts


def message_author(
    text:        str,          # np. "Dzień dobry,\nproszę ponowić…\nPrzykładsoft Sp. z o.o.\nOd: …"
    source_role: str,          # np. "klient" — rola z bazy albo z żądania; "" przy opisie
    vendors:     VendorNames,  # np. VendorNames(names=["Przykładsoft Sp. z o.o."])
) -> str:
    """
    Description:
    Ustala autora jednej wiadomości: `konsultant`, gdy tak zapisało ją źródło albo gdy we
    własnej części wiadomości, przed cytatem, stoi któraś nazwa dostawcy; w każdym innym
    przypadku `klient`. Nazwę porównuje się słowami, bez wielkości liter i interpunkcji.

    Example args:
        text="Dzień dobry,\\nproszę ponowić wysyłkę.\\nPrzykładsoft Sp. z o.o.\\nOd: Jan Kowalski"
        source_role="klient"
        vendors=VendorNames(names=["Przykładsoft Sp. z o.o."])

    Example result:
        "konsultant"
    """
    # Rolę konsultanta system zapisuje tylko przy odpowiedzi z helpdesku, więc jest pewna.
    if source_role == VENDOR_ROLE:
        return VENDOR_ROLE

    own = words_of(_own_part(text))

    for name in vendors.names:
        if _contains_run(own, words_of(name)):
            return VENDOR_ROLE

    return CLIENT_ROLE


def _own_part(text: str) -> str:   # np. "Proszę ponowić.\nPrzykładsoft Sp. z o.o.\nOd: Jan…"
    """
    Description:
    Oddaje własną część wiadomości: tekst do pierwszej linii nagłówka cytatu, przed którą stoją
    już co najmniej trzy słowa własnej treści (`MIN_OWN_WORDS`). Nagłówki przed nimi są
    pomijane: to nagłówek samej wiadomości albo przekazanie bez własnego tekstu („FYI”), po
    którym autora mówi podpis przekazanej wiadomości. Wiadomość bez cytatu jest cała własna.

    Example args:
        text="Proszę ponowić.\\nPrzykładsoft Sp. z o.o.\\nOd: Jan Kowalski\\nTemat: Błąd\\n…"

    Example result:
        "Proszę ponowić.\\nPrzykładsoft Sp. z o.o."
    """
    own:   list[str] = []
    words: int       = 0

    for line in text.split("\n"):
        header = QUOTE_HEADER.fullmatch(line) is not None

        # --- nagłówek po własnej treści: tu zaczyna się cytat ---
        if header and words >= MIN_OWN_WORDS:
            break

        # --- nagłówek przed własną treścią: należy do tej wiadomości, nie jest jej treścią ---
        if header:
            continue

        words += len(WORD.findall(line))
        own.append(line)

    return "\n".join(own)


def _contains_run(
    words: list[str],  # np. ["proszę", "ponowić", "przykładsoft", "sp", "z", "o", "o"]
    run:   list[str],  # np. ["przykładsoft", "sp", "z", "o", "o"]
) -> bool:
    """
    Description:
    Mówi, czy lista słów zawiera podany ciąg słów, kolejno, bez przerw.

    Example args:
        words=["proszę", "ponowić", "przykładsoft", "sp", "z", "o", "o"]
        run=["przykładsoft", "sp", "z", "o", "o"]

    Example result:
        True
    """
    width = len(run)

    return any(words[start:start + width] == run for start in range(len(words) - width + 1))
