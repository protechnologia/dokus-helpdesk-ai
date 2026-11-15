"""
Description:
Stałe golden setu zgłoszeń: pliki zestawu i korpusu odniesienia oraz progi obu pomiarów na nich —
wyszukiwania po znaczeniu i filtra jakości.
"""

import re
from pathlib import Path

# Golden set: wpis na każde zgłoszenie korpusu odniesienia z etykietą przeglądu (`useful`)
# i opcjonalnym zapytaniem, którego jest celem. Dane klienta, poza repo.
GOLDEN_FILE = Path("data/unsafe/golden/tickets-vector.json")

# Warstwy zapytań, po których `scripts/eval_embeddings.py` liczy wyniki osobno: rodzaj sprawy
# i trudność zapytania. Wartość spoza listy dałaby w tabeli pomiaru osobny wiersz.
QUERY_KINDS        = ("eksploatacyjne", "wdrożeniowo-migracyjne")
QUERY_DIFFICULTIES = ("typowe", "trudne")

# Dystraktory: zapytania bez odpowiednika w indeksie, na które poprawną odpowiedzią jest pusty
# wynik.
DISTRACTORS_FILE = Path("data/unsafe/golden/tickets-vector-distractors.json")

# Korpus odniesienia: karty 200 zgłoszeń golden setu, z których buduje się indeks do pomiarów.
# Sparsowane `gpt-6.1-sol` 2026-10-23; nowsze karty zastępują ten katalog dopiero po przyjęciu.
CORPUS_DIR = Path("data/unsafe/golden/cards")

# Kolekcja Qdranta z kartami korpusu odniesienia, osobna od kolekcji instancji (2026-11-13):
# instancja trzyma karty pełnego korpusu, a pomiar ma stać na 200 kartach golden setu.
GOLDEN_COLLECTION = "tickets_golden"

# Tabela Postgresa z wątkami golden setu (po anonimizacji, z `golden/anonymized/`), osobna od
# tabeli instancji z tego samego powodu co kolekcja (2026-11-15).
GOLDEN_TABLE = "tickets_text_golden"

# Podpowiedź do błędu pomiaru, gdy indeksu golden setu nie ma albo jest pusty: polecenie, które
# go buduje — ta sama komenda co indeks instancji, z nazwami kolekcji i tabeli podanymi
# w środowisku. Bez którejkolwiek przebudowa skasowałaby indeks instancji.
BUILD_HINT = (
    f"zbuduj indeks: QDRANT_COLLECTION={GOLDEN_COLLECTION} POSTGRES_TICKETS_TABLE={GOLDEN_TABLE} "
    "helpdesk tickets reindex data/unsafe/golden"
)

# Próg: zapytania, na które rekord-cel wraca jako pierwszy. Zmierzone 119 ze 126 (2026-10-23,
# karty `gpt-6.1-sol`); próg niżej, żeby wyłapać zepsutą ścieżkę, a nie zwykły dryf.
MIN_TARGET_FIRST = 115

# Próg: zapytania, na które rekord-cel w ogóle wraca. Zmierzone 126 ze 126.
MIN_TARGET_RETURNED = 123

# Próg: dystraktory z choć jednym trafieniem. Zmierzone 7 z 16 (na kartach Bielika 3 z 16).
# Trafienie na zapytanie bez odpowiednika wygląda na odpowiedź, a nią nie jest.
MAX_DISTRACTORS_WITH_HITS = 8

# Zestaw tekstowy: zapytania w kształcie `find_tickets_text` do wątków golden setu, z celem
# i bez celu (2026-11-15). Dane klienta, poza repo.
TEXT_FILE = Path("data/unsafe/golden/tickets-text.json")

# Wątki golden setu po anonimizacji, z których `reindex` buduje tabelę `GOLDEN_TABLE`.
THREADS_DIR = Path("data/unsafe/golden/anonymized")

# Warstwy zapytań tekstowych: kod błędu albo pliku, komunikat z ekranu, komunikat z logu albo
# biblioteki i nazwa funkcji albo dokumentu. Wartość spoza listy to literówka w zestawie.
TEXT_QUERY_KINDS = ("kod", "komunikat_ekran", "komunikat_log", "nazwa")

# Białe znaki, które baza sprowadza do jednej spacji po obu stronach szukania podciągiem: `\s`
# i twarda spacja, której `\s` bazy nie obejmuje. Na tym samym wzorcu test spójności zestawu
# sprawdza, że fraza stoi w wątku celu.
WHITESPACE = re.compile(r"[\s ]+")

# Oczekiwane wyniki pomiaru tekstowego (2026-11-15). Szukanie w zamrożonej tabeli jest
# deterministyczne, więc test porównuje je dokładnie: zmiana w dowolną stronę to zmiana
# w narzędziu, w bazie albo w zestawie, a nie dryf. Liczba zawyżona przez zepsuty pomiar też
# wychodzi, czego próg „co najmniej” by nie złapał.

# Zapytania, na które zgłoszenie-cel wraca jako pierwsze: 21 z 23. Nie wraca pierwsze częsty
# komunikat, którego wątek-cel jest najstarszy, i fraza bez polskich znaków.
TEXT_TARGET_FIRST = 21

# Zapytania, na które zgłoszenie-cel w ogóle wraca: 22 z 23. Chybia fraza bez polskich znaków.
TEXT_TARGET_RETURNED = 22

# Zapytania bez celu z choć jednym trafieniem: 0 z 6.
TEXT_DISTRACTORS_WITH_HITS = 0

# Próg: rekordy oznaczone w przeglądzie jako bez wiedzy, które filtr odrzuca. Zmierzone 59 z 65
# (2026-10-23, karty `gpt-6.1-sol`); próg niżej, żeby wyłapać filtr, który zamilkł, a nie dryf.
MIN_LABELLED_DROPS = 55

# Próg: rekordy uznane w przeglądzie za dobre, które filtr odrzuca. Zmierzone 0 ze 135. Fałszywy
# alarm jest droższą pomyłką: dobry rekord znika z indeksu niezauważony.
MAX_FALSE_POSITIVES = 2
