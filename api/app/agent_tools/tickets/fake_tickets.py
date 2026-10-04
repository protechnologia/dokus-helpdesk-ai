"""
Description:
Zmyślone zgłoszenia, na których stoją atrapy wszystkich narzędzi zgłoszeń (`find_tickets_vector`,
`find_tickets_text`, `read_tickets_card`, `read_tickets_thread`). Jedno miejsce, żeby numer
zwrócony przez atrapę wyszukiwania dało się odczytać atrapą odczytu — tak jak na produkcji.

| numer | karta | wątek | po co jest w zestawie                                          |
|-------|-------|-------|----------------------------------------------------------------|
| 90001 | tak   | tak   | ten sam objaw, przyczyna pierwsza: zacięta kolejka             |
| 90002 | tak   | tak   | ten sam objaw, przyczyna druga: plik blokady                   |
| 90003 | tak   | tak   | ten sam objaw, przyczyna trzecia: za duży załącznik            |
| 90011 | nie   | tak   | komunikat z ekranu; zgłoszenie bez karty                       |
| 90012 | tak   | tak   | ten sam komunikat, inna przyczyna: brak sekwencji numeracji    |

O czym pamiętać przy zmianach:

- Treść jest wymyślona, nigdy kopiowana z korpusu; wątki są już „po anonimizacji"
  (`{KLIENT_1}`).
- Numery są stałe: atrapy wyszukiwań i testy grafów odwołują się do nich wprost.
- Wątek ma kształt `RawTicket.as_thread()` — tak leży w tabeli wyszukiwania.
- Zgłoszenie bez karty (90011) to stan poprawny: wątek ma każde zgłoszenie, kartę tylko to,
  które przeszło parsowanie i filtr jakości.
"""

from datetime import date

from app.core_model.ticket_parsed import ParsedTicket
from app.db_postgres.row.tickets import TicketRow

QUEUE_THREAD = "\n".join([
    "ZGŁOSZENIE 90001 z 2026-02-10",
    "Temat: Brak przesyłek z e-Doręczeń",
    "",
    "OPIS ZGŁASZAJĄCEGO:",
    "Od wczoraj w skrzynce e-Doręczeń nie ma nowych przesyłek, a nadawcy potwierdzają wysyłkę.",
    "",
    "KOMENTARZ 1 — konsultant, 2026-02-10 09:30:00 (typ: zwyczajny):",
    "Od kiedy dokładnie brak przesyłek i czy dotyczy to wszystkich skrzynek?",
    "",
    "KOMENTARZ 2 — klient, 2026-02-10 09:50:00 (typ: zwyczajny):",
    "Od wczorajszego popołudnia, we wszystkich.",
    "",
    "KOMENTARZ 3 — konsultant, 2026-02-10 10:40:00 (typ: rozwiazanie):",
    "Kolejka pobierania zacięła się po przerwanym połączeniu. Zrestartowaliśmy ją, zaległe",
    "przesyłki pobrały się same.",
])
LOCK_FILE_THREAD = "\n".join([
    "ZGŁOSZENIE 90002 z 2026-04-22",
    "Temat: e-Doręczenia nic nie pobierają",
    "",
    "OPIS ZGŁASZAJĄCEGO:",
    "Po ostatniej aktualizacji nie przychodzą przesyłki z e-Doręczeń.",
    "",
    "KOMENTARZ 1 — konsultant, 2026-04-22 13:10:00 (typ: rozwiazanie):",
    "Po aktualizacji został plik blokady, który wstrzymywał pobieranie. Usunęliśmy go.",
    "Po kolejnej aktualizacji proszę sprawdzić, czy nie wraca.",
])
ATTACHMENT_THREAD = "\n".join([
    "ZGŁOSZENIE 90003 z 2026-06-03",
    "Temat: Nie przychodzą e-Doręczenia",
    "",
    "OPIS ZGŁASZAJĄCEGO:",
    "Skrzynka e-Doręczeń stoi od dwóch dni, nadawcy twierdzą, że wysłali.",
    "",
    "KOMENTARZ 1 — konsultant, 2026-06-03 11:00:00 (typ: zwyczajny):",
    "Jak duże załączniki miały ostatnie przesyłki?",
    "",
    "KOMENTARZ 2 — konsultant, 2026-06-03 14:20:00 (typ: rozwiazanie):",
    "Jedna przesyłka miała załącznik ponad limit operatora i zatrzymała pobieranie całej",
    "skrzynki. Trzeba ją odebrać ręcznie u operatora; po naszej stronie bez zmian.",
])
SIGNING_THREAD = "\n".join([
    "ZGŁOSZENIE 90011 z 2026-03-02",
    "Temat: Błąd przy podpisie",
    "",
    "OPIS ZGŁASZAJĄCEGO:",
    "Dzień dobry, przy podpisywaniu pisma z dużym załącznikiem (skan, ok. 40 MB) wyskakuje",
    "„Nie udało się skomunikować z serwerem”. Mniejsze pliki podpisują się bez problemu.",
    "Pozdrawiam, {KLIENT_1}",
    "",
    "KOMENTARZ 1 — konsultant, 2026-03-02 11:20:00 (typ: rozwiazanie):",
    "Podnieśliśmy limity zasobów serwera, podpis dużych plików już działa.",
])
NUMBERING_THREAD = "\n".join([
    "ZGŁOSZENIE 90012 z 2026-01-05",
    "Temat: Nie da się zapisać pisma",
    "",
    "OPIS ZGŁASZAJĄCEGO:",
    "Od 2 stycznia zapis pisma kończy się „Nie udało się skomunikować z serwerem”.",
    "W grudniu wszystko działało.",
    "",
    "KOMENTARZ 1 — konsultant, 2026-01-05 09:05:00 (typ: zwyczajny):",
    "Czy błąd pojawia się przy każdym rejestrze, czy tylko w kancelarii?",
    "",
    "KOMENTARZ 2 — klient, 2026-01-05 09:40:00 (typ: zwyczajny):",
    "Przy każdym.",
    "",
    "KOMENTARZ 3 — konsultant, 2026-01-05 10:15:00 (typ: rozwiazanie):",
    "Brakowało sekwencji numeracji na 2026 rok. Założyliśmy ją, zapis działa.",
])


def default_cards() -> list[ParsedTicket]:
    """
    Description:
    Cztery zmyślone karty. Pierwsze trzy to jeden objaw („nie przychodzą przesyłki
    z e-Doręczeń") i trzy różne przyczyny — najczęstszy kształt trafień w tym korpusie, na którym
    agent ma dopytywać zamiast zgadywać. Czwarta należy do zgłoszenia znajdowanego po dosłownym
    komunikacie.

    Example args:
        (brak)

    Example result:
        [ParsedTicket(ticket_id="90001", …), ParsedTicket(ticket_id="90002", …), …]
    """
    no_mail = {
        "component":                     "e-Doręczenia",
        "problem":                       "Nie przychodzą przesyłki z e-Doręczeń",
        "symptoms":                      "Brak nowych przesyłek, choć nadawcy potwierdzają wysyłkę",
        "error_codes":                   [],
        "resolution_vocabulary_version": 1,
    }

    cards = [
        ParsedTicket(
            **no_mail,
            ticket_id         = "90001",
            date              = date(2026, 2, 10),
            cause             = "Zacięta kolejka pobierania po przerwanym połączeniu",
            solution          = "Zrestartowano kolejkę; zaległe przesyłki pobrały się same.",
            resolution        = "naprawione",
            questions_summary = "pytano, od kiedy brak przesyłek i czy dotyczy wszystkich skrzynek",
        ),
        ParsedTicket(
            **no_mail,
            ticket_id         = "90002",
            date              = date(2026, 4, 22),
            cause             = "Plik blokady pozostawiony po aktualizacji blokował pobieranie",
            solution          = "Usunięto plik blokady; po aktualizacji sprawdzić, czy nie wraca.",
            resolution        = "naprawione",
            questions_summary = "pytano, czy problem zaczął się po aktualizacji",
        ),
        ParsedTicket(
            **no_mail,
            ticket_id         = "90003",
            date              = date(2026, 6, 3),
            cause             = "Załącznik ponad limit operatora zatrzymał pobieranie skrzynki",
            solution          = "Przesyłkę z dużym załącznikiem odebrano ręcznie u operatora.",
            resolution        = "bez_zmian_w_systemie",
            questions_summary = "pytano o rozmiar załączników w ostatnich przesyłkach",
        ),
        ParsedTicket(
            ticket_id         = "90012",
            date              = date(2026, 1, 5),
            component         = "główna aplikacja",
            problem           = "Zapis pisma kończy się błędem komunikacji z serwerem",
            symptoms          = "Od 2 stycznia przy zapisie pisma komunikat o braku komunikacji",
            error_codes       = ["Nie udało się skomunikować z serwerem"],
            cause             = "Brak sekwencji numeracji na nowy rok",
            solution          = "Założono sekwencję numeracji na 2026 rok; zapis działa.",
            resolution        = "naprawione",
            questions_summary = "pytano, czy błąd dotyczy każdego rejestru, czy tylko kancelarii",
            resolution_vocabulary_version = 1,
        ),
    ]

    return cards


def default_threads() -> list[TicketRow]:
    """
    Description:
    Pięć zmyślonych wątków — każde zgłoszenie z zestawu ma wątek, także to bez karty. Wracają
    jako wiersze tabeli wyszukiwania, czyli w kształcie, w jakim wątki leżą w Postgresie; temat
    jest wycinany z linii „Temat:" wątku.

    Example args:
        (brak)

    Example result:
        [TicketRow(ticket_id="90001", subject="Brak przesyłek z e-Doręczeń", …), …]
    """
    rows = [
        TicketRow.from_thread("90001", date(2026, 2, 10), QUEUE_THREAD),
        TicketRow.from_thread("90002", date(2026, 4, 22), LOCK_FILE_THREAD),
        TicketRow.from_thread("90003", date(2026, 6, 3),  ATTACHMENT_THREAD),
        TicketRow.from_thread("90011", date(2026, 3, 2),  SIGNING_THREAD),
        TicketRow.from_thread("90012", date(2026, 1, 5),  NUMBERING_THREAD),
    ]

    return rows
