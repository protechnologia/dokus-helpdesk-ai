"""
Description:
Stałe golden setu zgłoszeń: pliki zestawu i korpusu odniesienia oraz progi obu pomiarów na nich —
wyszukiwania po znaczeniu i filtra jakości.
"""

from pathlib import Path

# Zapytania golden setu, każde ze wskazanym rekordem-celem, i etykiety przeglądu korpusu
# (`rejected`: rekordy bez wiedzy). Dane klienta, poza repo.
GOLDEN_FILE = Path("data/unsafe/golden/tickets.json")

# Dystraktory: zapytania bez odpowiednika w indeksie, na które poprawną odpowiedzią jest pusty
# wynik.
DISTRACTORS_FILE = Path("data/unsafe/golden/tickets-distractors.json")

# Korpus odniesienia: 200 sparsowanych zgłoszeń, z których zbudowano indeks i etykiety; ma przetrwać
# masowy import (p. 31).
CORPUS_DIR = Path("data/unsafe/parsed/bielik-11b-golden200")

# Podpowiedź do błędu pomiaru, gdy kolekcja zgłoszeń jest pusta: polecenie, które ją buduje.
BUILD_HINT = "zbuduj indeks: helpdesk tickets index data/unsafe/parsed/bielik-11b-golden200"

# Próg: zapytania, na które rekord-cel wraca jako pierwszy. Zmierzone 152 ze 162; próg niżej, żeby
# wyłapać zepsutą ścieżkę, a nie zwykły dryf.
MIN_TARGET_FIRST = 145

# Próg: zapytania, na które rekord-cel w ogóle wraca. Zmierzone 160 ze 162: jeden cel wypada poza
# pierwszą piątkę, jeden odcina próg.
MIN_TARGET_RETURNED = 155

# Próg: dystraktory z choć jednym trafieniem. Zmierzone 3 z 16. Trafienie na zapytanie bez
# odpowiednika wygląda na odpowiedź, a nią nie jest.
MAX_DISTRACTORS_WITH_HITS = 5

# Próg: rekordy oznaczone w przeglądzie jako bez wiedzy, które filtr odrzuca. Zmierzone 29 z 38;
# próg niżej, żeby wyłapać filtr, który zamilkł, a nie zwykły dryf.
MIN_LABELLED_DROPS = 25

# Próg: rekordy uznane w przeglądzie za dobre, które filtr odrzuca. Zmierzone 0. Fałszywy alarm
# jest droższą pomyłką: dobry rekord znika z indeksu niezauważony.
MAX_FALSE_POSITIVES = 2
