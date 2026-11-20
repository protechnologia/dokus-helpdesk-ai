"""
Description:
Zmyślone maile do testów usuwania powtórzeń, reguły autora i normalizera maili. Przykłady
usuwania powtórzeń to przykłady z notatki o metodzie (p. 32): mail i odpowiedź, która go
cytuje. Pakiet helpera tego pliku nie wystawia — test importuje próbki z tego modułu.
"""

# Zdanie z 10 słowami, za długie na zwrot i za krótkie na powtórzenie: od 12 słów liczy się
# ciąg powtórzony.
SENTENCE = "Od wczoraj nie możemy wysłać żadnego pisma do ePUAP."

# Podpis klienta w zmyślonych mailach.
SIGNATURE = "Pozdrawiam\nJan Kowalski"


def sample_quote() -> tuple[str, str, str]:
    """
    Description:
    Mail, odpowiedź z jego cytatem i odpowiedź, w której zostaje sama nowa treść: obie linie
    cytatu leżą w ciągu 12 słów, który stał już w mailu.

    Example args:
        (brak)

    Example result:
        ("Co tam słychać?\\nOd wczoraj…", "Skrzynka ePUAP…\\n> Co tam słychać?\\n…", "Skrzynka…")
    """
    mail     = f"Co tam słychać?\n{SENTENCE}"
    reply    = (
        "Skrzynka ePUAP wymaga ponownej autoryzacji, proszę ją odnowić.\n"
        f"> Co tam słychać?\n> {SENTENCE}"
    )
    expected = "Skrzynka ePUAP wymaga ponownej autoryzacji, proszę ją odnowić."

    return mail, reply, expected


def sample_reflowed_quote() -> tuple[str, str]:
    """
    Description:
    Mail i cytat tej samej treści złamany inaczej, małymi literami, z myślnikiem zamiast
    dwukropka i bez cudzysłowów: znika cały.

    Example args:
        (brak)

    Example result:
        ("Od wczoraj… Komunikat: „Brak uprawnień”.", "> od wczoraj…\\n> pisma do epuap - …")
    """
    mail  = f"{SENTENCE} Komunikat: „Brak uprawnień”."
    reply = "> od wczoraj nie możemy wysłać żadnego\n> pisma do epuap - komunikat brak uprawnień"

    return mail, reply


def sample_quote_with_new_word() -> tuple[str, str, str]:
    """
    Description:
    Mail z trzech linii i jego cytat z dopisanym „nadal” w drugiej linii. Pierwsza linia
    zostaje, bo przed „nadal” stoi tylko 10 słów ciągu; druga, bo niesie nowe słowo; trzecia
    znika, bo za „nadal” ciąg ma 15 słów.

    Example args:
        (brak)

    Example result:
        ("Od wczoraj…\\nKomunikat brzmi…\\nProsimy…", "> Od wczoraj…\\n> Komunikat nadal…\\n…", …)
    """
    mail = (
        f"{SENTENCE}\n"
        "Komunikat brzmi: Brak uprawnień do skrzynki podawczej.\n"
        "Prosimy o pilną pomoc, bo pisma czekają w kolejce."
    )
    reply = (
        f"> {SENTENCE}\n"
        "> Komunikat nadal brzmi: Brak uprawnień do skrzynki podawczej.\n"
        "> Prosimy o pilną pomoc, bo pisma czekają w kolejce."
    )
    expected = f"> {SENTENCE}\n> Komunikat nadal brzmi: Brak uprawnień do skrzynki podawczej."

    return mail, reply, expected


def sample_quote_without_extra_word() -> tuple[str, str]:
    """
    Description:
    Mail zaczynający się od „Niestety” i jego cytat bez tego słowa: słowo dodatkowe w oryginale
    niczego nie zmienia, cytat znika cały.

    Example args:
        (brak)

    Example result:
        ("Niestety od wczoraj…\\nKomunikat brzmi…", "> Od wczoraj…\\n> Komunikat brzmi…")
    """
    mail  = (
        "Niestety od wczoraj nie możemy wysłać żadnego pisma do ePUAP.\n"
        "Komunikat brzmi: Brak uprawnień do skrzynki podawczej."
    )
    reply = f"> {SENTENCE}\n> Komunikat brzmi: Brak uprawnień do skrzynki podawczej."

    return mail, reply


def sample_quote_without_polish_letters() -> tuple[str, str]:
    """
    Description:
    Zdanie z 13 słowami i jego cytat bez polskich znaków: litery się różnią, więc cytat zostaje.

    Example args:
        (brak)

    Example result:
        ("Od wczoraj nie możemy…", "> Od wczoraj nie mozemy…")
    """
    mail  = "Od wczoraj nie możemy wysłać żadnego pisma do skrzynki ePUAP naszego urzędu gminy."
    reply = "> Od wczoraj nie mozemy wyslac zadnego pisma do skrzynki ePUAP naszego urzedu gminy."

    return mail, reply


def sample_doubled_mail() -> tuple[str, str]:
    """
    Description:
    Mail zapisany w jednym polu dwa razy, jak w kanale „Automat mailowy” (wersja HTML i zwykły
    tekst), z drugą kopią złamaną inaczej, oraz to, co z niego zostaje: pierwsza kopia.

    Example args:
        (brak)

    Example result:
        ("Dzień dobry,\\nod wczoraj…\\nDzień dobry,\\nod wczoraj…", "Dzień dobry,\\nod wczoraj…")
    """
    first   = f"Dzień dobry,\nod wczoraj nie możemy wysłać żadnego pisma do ePUAP.\n{SIGNATURE}"
    doubled = (
        f"{first}\n"
        "Dzień dobry, od wczoraj nie możemy wysłać\n"
        "żadnego pisma do ePUAP. Pozdrawiam Jan Kowalski"
    )

    return doubled, first


def sample_vendor_reply() -> str:
    """
    Description:
    Odpowiedź dostawcy z podpisem z nazwą firmy, nad cytatem maila klienta.

    Example args:
        (brak)

    Example result:
        "Dzień dobry,\\nproszę ponowić wysyłkę.\\nZ poważaniem\\nAnna Nowak\\nPrzykładsoft…"
    """
    reply = (
        "Dzień dobry,\nproszę ponowić wysyłkę po nadaniu uprawnienia.\n"
        "Z poważaniem\nAnna Nowak\nPrzykładsoft Sp. z o.o.\n"
        "Od: Jan Kowalski\nTemat: Błąd wysyłki\n> Nie działa wysyłka."
    )

    return reply


def sample_client_reply_quoting_vendor() -> str:
    """
    Description:
    Odpowiedź klienta bez nazwy dostawcy we własnej treści, nad cytatem odpowiedzi dostawcy
    z jej podpisem.

    Example args:
        (brak)

    Example result:
        "Dziękuję, wysyłka już działa.\\nJan Kowalski\\nOd: Anna Nowak\\n…\\n> Przykładsoft…"
    """
    reply = (
        "Dziękuję, wysyłka już działa.\nJan Kowalski\n"
        "Od: Anna Nowak\nWysłano: 3 lipca 2026 11:02\n"
        "> Proszę ponowić wysyłkę.\n> Przykładsoft Sp. z o.o."
    )

    return reply


def sample_forward() -> str:
    """
    Description:
    Przekazanie bez własnej treści („FYI”) wiadomości dostawcy, która niesie jego podpis.

    Example args:
        (brak)

    Example result:
        "FYI\\nOd: Anna Nowak\\nTemat: Zapowiedź aktualizacji\\nW sobotę zainstalujemy…"
    """
    forward = (
        "FYI\nOd: Anna Nowak\nTemat: Zapowiedź aktualizacji\n"
        "W sobotę zainstalujemy nową wersję aplikacji.\nPrzykładsoft Sp. z o.o."
    )

    return forward


def sample_mail_with_own_header() -> str:
    """
    Description:
    Wiadomość dostawcy zapisana razem ze swoim nagłówkiem: nagłówek stoi na samym początku
    pola, przed własną treścią z podpisem.

    Example args:
        (brak)

    Example result:
        "Od: Anna Nowak\\nDo: Urząd Gminy Przykładowo\\nTemat: Aktualizacja\\nW sobotę…"
    """
    mail = (
        "Od: Anna Nowak\nDo: Urząd Gminy Przykładowo\nTemat: Aktualizacja\n"
        "W sobotę zainstalujemy nową wersję aplikacji.\nPRZYKŁADSOFT sp.z o.o."
    )

    return mail


def sample_cleaned_thread() -> str:
    """
    Description:
    Wątek zmyślony 41101 z `data/safe/mail/raw-db/` po normalizerze, w kształcie
    `RawTicket.as_thread()`: opis klienta raz, bez drugiej kopii, odpowiedź dostawcy bez stopki,
    bez odwołania do obrazka i bez cytatu, z rolami z podpisów. Klauzula RODO urzędu stoi
    w jednym wątku, więc szablonem nie jest i zostaje.

    Example args:
        (brak)

    Example result:
        "ZGŁOSZENIE 41101 z 2026-07-03\\nTemat: Błąd wysyłki\\n\\nOPIS ZGŁASZAJĄCEGO — klient:\\n…"
    """
    thread = (
        "ZGŁOSZENIE 41101 z 2026-07-03\n"
        "Temat: Błąd wysyłki\n"
        "\n"
        "OPIS ZGŁASZAJĄCEGO — klient:\n"
        "Dzień dobry,\n"
        "od wczoraj nie możemy wysłać żadnego pisma do ePUAP.\n"
        "Przy wysyłce pojawia się komunikat „Brak uprawnień do skrzynki podawczej”.\n"
        "Pozdrawiam\n"
        "Jan Kowalski\n"
        "Urząd Gminy Przykładowo\n"
        "Administratorem Pani/Pana danych osobowych jest Wójt Gminy\n"
        "Przykładowo, ul. Przykładowa 1, kontakt: iod@przykladowo.example.pl.\n"
        "\n"
        "KOMENTARZ 1 — konsultant, 2026-07-03 10:40:00 (typ: zwyczajny):\n"
        "Dzień dobry,\n"
        "po aktualizacji trzeba ponownie nadać uprawnienie do skrzynki\n"
        "ePUAP: Administracja → Skrzynki → Uprawnienia. Wysyłki z błędem\n"
        "proszę ponowić dopiero po nadaniu uprawnienia.\n"
        "Z poważaniem\n"
        "Anna Nowak\n"
        "Specjalista ds. help desk | Przykładsoft Sp. z o.o.\n"
        "Od: Jan Kowalski\n"
        "Wysłano: 3 lipca 2026 10:12\n"
        "Temat: Błąd wysyłki"
    )

    return thread
