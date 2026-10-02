"""
Description:
Reguły filtra jakości — jedna funkcja na regułę, każda zwraca fragment, który ją wyzwolił, albo
None.

Dlaczego osobno od `filter_ticket_quality.py`: reguł wciąż przybywa (każdy pomiar na większym
korpusie podsuwa kolejną), a orkiestrator wokół nich praktycznie się nie zmienia. Dwa pliki, dwa
rytmy zmian.

Dlaczego zwykłe funkcje, a nie metody: każda to bezstanowy odczyt jednego rekordu, więc klasa
dałaby tylko miejsce na `self` (CLAUDE.md -> „Warstwy kodu": o funkcji czy klasie rozstrzyga
stan). `RULES` na dole to to, po czym iteruje orkiestrator, więc sam nie nazywa żadnej reguły,
a dołożenie reguły to dopisanie do krotki.

**Każda reguła czyta `solution`, nigdy `cause` — to zmierzone, nie założone.** Puste `cause`
wygląda na oczywisty sygnał, a nim nie jest: 114 z 200 zmierzonych rekordów nie deklaruje
przyczyny, a 105 z nich jest w pełni dobrych (2026-08-13). Zgłoszenia bywają rozwiązane bez
nazwania przyczyny, więc filtr oparty na tym polu wypatroszyłby korpus.

**Etykiety, wobec których mierzono te reguły, nie są niezależną prawdą** — wytworzył je model
czytający te same artefakty. Liczby niżej mierzą więc ZGODNOŚĆ z wcześniejszym przeglądem, nie
poprawność; rozbieżności to rekordy warte ludzkiego oka, nie dowód, że reguły są złe.
"""

import re

# Jawne sposoby schematu na „nic tu nie ma" (NO_VALUE, NOT_APPLICABLE w `model/ticket_parsed.py`)
# plus dwa sformułowania, które prompt parsujący wytwarza obok nich.
#
# NA TYM STOI CAŁA REGUŁA: czyta KONTRAKT, nie prozę modelu. Każde pole może powiedzieć „brak"
# zamiast zostać pominięte, prompt parsujący leży w repo pod testem-strażnikiem i celowo nie jest
# konfigurowalny (zasada 7). Inny model dostaje ten sam prompt z tymi samymi frazami ucieczkowymi,
# więc w przeciwieństwie do reguły strojonej pod manierę jednego modelu ta przeżywa jego podmianę.
# Edycja tych fraz w prompcie JEST edycją tego filtra; plik promptu mówi to wprost, a test-strażnik
# na korpusie odniesienia głośno pada, gdy oba się rozjadą.
#
# `brak` dopasowujemy jako CAŁE SŁOWO, nigdy jako prefiks. „Dodano brakujące ustawienie systemowe"
# opisuje wykonaną pracę, a `brak\w*` robiło z tego odrzucenie (zmierzone: jeden fałszywy alarm,
# zniknął po tej zmianie).
ESCAPE_PHRASE = re.compile(r"\b(brak|nie dotyczy|nie ustalono|nie podano)\b", re.I)

# Ile słów może zostać obok frazy ucieczkowej, zanim pole liczy się jako treść.
#
# Zmierzone na korpusie odniesienia z 200 rekordów (2026-08-13): przy tym progu reguła odrzuca 29
# z 38 oznaczonych rekordów przy ZERZE fałszywych alarmów, a każda wartość od 4 do 10 daje ten sam
# czysty podział — szeroki margines, nie liczba dopasowana do danych. Rozumowanie jest proste:
# pusty rekord mówi „brak rozstrzygnięcia w wątku" i na tym kończy, a ODMOWA — najcenniejsza klasa
# w tym korpusie, bo mówi czytelnikowi, czego NIE próbować — musi się wytłumaczyć, więc wychodzi
# długa („Brak możliwości wygenerowania ZPO w tej sytuacji. Klient musi zaakceptować…").
#
# Tę liczbę trzeba będzie przejrzeć na pełnym korpusie; należy do tego korpusu i tego parsera,
# dlatego jest nazwaną stałą, a nie literałem zakopanym w porównaniu.
MAX_HOLLOW_EXTRA_WORDS = 10

# Ile pola trafia do raportu. Dość, by rozpoznać zdanie, i dość mało, by przebieg na 200 rekordach
# dało się czytać.
EVIDENCE_LENGTH = 80


def no_resolution(
    solution: str,  # np. "Brak rozstrzygnięcia w wątku."
) -> str | None:
    """
    Description:
    Odpala, gdy `solution` przyznaje, że rozstrzygnięcia nie ma, i niewiele poza tym dodaje —
    rekord kończy się bez powiedzenia, co było nie tak ani co zrobiono, więc nie ma czego
    zaproponować nikomu innemu.

    Dwa kroki, a bezpieczną czyni ją drugi: znajdź frazę ucieczkową gdziekolwiek w polu, potem
    policz, co zostaje po usunięciu słów ucieczki. Zostało mało — pole jest puste; zostało dużo —
    „brak" otwiera realne stwierdzenie (odmowę, wyjaśnienie niezmienionego zachowania) i rekord
    zostaje.

    Zmierzone: 29 z 38 oznaczonych odrzuceń, bez fałszywych alarmów (2026-08-13).

    Example args:
        solution="Brak rozstrzygnięcia w wątku."

    Example result:
        "Brak rozstrzygnięcia w wątku."

    Example args:
        solution="Brak możliwości wygenerowania ZPO w tej sytuacji. Klient musi zaakceptować…"

    Example result:
        None — odmowa to treść, nie pustka
    """
    # --- czy rekord przyznaje, że nic nie ma? ---
    if not ESCAPE_PHRASE.search(solution):
        return None

    # --- ile zostaje po wyjęciu przyznania? ---
    # Ten sam wzorzec i znajduje przyznanie, i je usuwa: osobną listę „pustych słów" zmierzono
    # wobec niego i przy wybranym progu nic nie dała (identyczne 29/38, zero fałszywych alarmów),
    # więc była tylko kolejną rzeczą do synchronizowania, bez zysku.
    remainder = ESCAPE_PHRASE.sub(" ", solution)

    if len(re.findall(r"\w+", remainder)) > MAX_HOLLOW_EXTRA_WORDS:
        return None

    return solution.strip()[:EVIDENCE_LENGTH]


# Wszystkie reguły, w kolejności, w jakiej wypisuje je raport. Orkiestrator iteruje po tej krotce
# i nie zna żadnej reguły z nazwy, więc dołożenie reguły to dopisanie tutaj — a testy
# parametryzują się po niej, a nie po zaszytej liczbie.
#
# Dziś jedna reguła, celowo. Wzorce dla pozostałych dziewięciu odrzuceń (obietnica w czasie
# przyszłym, odesłanie do zgłoszenia-duplikatu, zgłoszenie niosące kilka niepowiązanych spraw)
# łapały po jeden–dwa rekordy, zależąc od dokładnego sformułowania jednego modelu — krucha strona
# wymiany, za ułamek uzysku. Wrócą, jeśli większy korpus pokaże, że są tego warte.
RULES = (
    no_resolution,
)
