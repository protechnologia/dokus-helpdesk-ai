"""
Description:
Stałe golden setu kanału „Automat mailowy”: pliki zestawu, wątki źródłowe, słownik maili
instancji, etykiety linii i progi pomiaru czyszczenia (p. 32.3). Progi stoją obok liczb
zmierzonych 2026-11-20 ze słownikiem z tego dnia, z małym zapasem: przebudowany słownik je
przesuwa.
"""

from pathlib import Path

# Golden set kanału: etykiety wątków z 32.1 (rodzaj, `useful`) i pola wątku, każde z autorem
# i oznaczeniami linii z 32.3. Dane klienta, poza repo.
GOLDEN_FILE = Path("data/unsafe/golden/service-tickets-mail.json")

# Wątki źródłowe: pliki eksportu sierpniowego zrzutu, z których powstały obie warstwy etykiet.
RAW_DB_DIR = Path("data/unsafe/corpus/raw-db")

# Słownik maili instancji, którym normalizer czyści wątki: szablony i nazwy dostawcy.
MAIL_DIR = Path("data/unsafe/mail")

# Etykiety linii w kolejności, w jakiej rozstrzyga instrukcja oznaczania: pierwsza pasująca
# wygrywa.
LABELS = ("stopka", "naglowek", "kopia", "podpis", "tresc")

# Etykiety linii, które czyszczenie ma usunąć: tekst, który stał już wyżej, i stałe formułki.
JUNK_LABELS = ("kopia", "stopka")

# Etykieta linii, która ma zostać: własna treść wiadomości i treść cytatu, którego wyżej nie ma.
CONTENT_LABEL = "tresc"

# Rola, którą normalizer ma ustalić dla autora z etykiety 32.1. Autor „system” (automatyczne
# powiadomienie) roli nie ma, więc liczy się jako niezgodność, a pole puste („brak”) się pomija.
ROLE_OF_AUTHOR = {
    "dostawca": "konsultant",
    "klient":   "klient",
}

# Próg: udział pól, w których rola z reguły autora zgadza się z autorem z 32.1. Zmierzone 353 z 367
# (96,2%, 2026-11-20); role z bazy dają 51%.
MIN_ROLE_SHARE = 0.95

# Próg: udział słów, które zostają po czyszczeniu. Zmierzone 27,5% (25 127 z 91 332).
MAX_KEPT_WORD_SHARE = 0.30

# Próg: linie treści usunięte w wątkach z wiedzą. Zmierzone 3: tło masowego maila dostawcy
# w 34722 („aktualizacja przebiegła pomyślnie”), który jest w całości szablonem; dopisane do niego
# zdanie z wiedzą zostaje.
MAX_LOST_LINES_IN_USEFUL = 3

# Próg: udział słów treści usuniętych we wszystkich wątkach. Zmierzone 1,0% (147 z 14 754), z czego
# prawie wszystko to ten sam masowy mail w 12 wątkach.
MAX_LOST_CONTENT_SHARE = 0.02

# Próg: udział śmieci (kopia, stopka) wśród słów, które zostały. Zmierzone 18,7% (4691 z 25 127),
# głównie stopki urzędów przy pierwszym wystąpieniu, których słownik nie zna.
MAX_JUNK_SHARE = 0.20
