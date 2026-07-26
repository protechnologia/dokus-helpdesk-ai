# dokus-helpdesk-ai — podsumowanie projektu

Założenia i decyzje architektoniczne.

## Co budujemy

Asystenta opartego na dużym modelu językowym (LLM), który wspiera wdrożeniowców pracujących
z aplikacją helpdesk. Punktem wyjścia jest **historyczna baza zgłoszeń** — setki spraw, które
ktoś już kiedyś rozwiązał. Ta wiedza formalnie jest dostępna, ale w praktyce leży odłogiem:
wyszukiwanie po słowach zawodzi, bo tę samą awarię każdy klient opisuje innymi słowami,
a nikt nie przegląda archiwum przy każdym nowym zgłoszeniu.

Docelowy efekt: wdrożeniowiec dostaje nowe zgłoszenie, a system **od razu podsuwa gotowy
projekt odpowiedzi**, oparty na tym, jak rozwiązano podobne sprawy w przeszłości — wraz
z odnośnikami do konkretnych historycznych zgłoszeń, na których się oparł.

**Wartość biznesowa:** krótszy czas reakcji, mniejsza zależność od pamięci najbardziej
doświadczonych osób, szybsze wdrożenie nowych pracowników do zespołu, spójność odpowiedzi.

## Jak to działa — trzy kroki

**1. Zgłoszenia trafiają do kanonicznej postaci.** Zamiast wrzucać do wyszukiwarki surowe treści,
każdą historyczną konwersację przepuszczamy **jednorazowo** przez model językowy, który wyciąga
z niej ustrukturyzowaną kartę sprawy:

| Pole | Co zawiera | Do czego służy |
|---|---|---|
| Numer zgłoszenia | identyfikator w systemie źródłowym | odnośnik do oryginału |
| Data | kiedy sprawa wpłynęła | kontekst — starsze rozwiązania bywają nieaktualne |
| System / moduł | np. „moduł fakturowania" | **wyszukiwanie** |
| Problem | sedno sprawy w 1–2 zdaniach | **wyszukiwanie** |
| Objawy | co widzi użytkownik | **wyszukiwanie** |
| Kody błędów, numery urządzeń | np. „E-104", numer terminala | wyszukiwanie po symbolach (etap 8) |
| Przyczyna | co okazało się źródłem problemu | treść odpowiedzi |
| Rozwiązanie | co konkretnie pomogło | treść odpowiedzi |
| Kategoria | pozycja ze słownika | filtrowanie i statystyki |
| Czy rozwiązane | tak / nie | tylko rozwiązane trafiają do indeksu |
| Czy potwierdzone przez klienta | tak / nie | podnosi wagę trafienia |

Uwaga nieoczywista: **wyszukujemy wyłącznie po polach opisujących problem** (system, problem,
objawy). Rozwiązanie celowo nie bierze udziału w porównaniu — szukamy spraw o podobnym
*problemie*, a nie o podobnym *rozwiązaniu*, więc mieszanie obu sygnałów pogorszyłoby trafność.

To jest najważniejsza decyzja projektowa. Surowa konwersacja to w dużej mierze szum — powitania,
stopki, historia wątku, dygresje. Wyszukiwanie po takim tekście gubi sedno sprawy. Po sprowadzeniu
do kanonicznej postaci porównujemy problem z problemem, a nie zgłoszenie ze zgłoszeniem.

Dodatkowa korzyść: te karty sprawy zapisujemy jako **trwały zasób firmy** (pliki na dysku).
Powstają raz i przeżywają każdą późniejszą zmianę technologii — gdy za rok pojawi się lepszy
model wyszukiwania, przebudowujemy indeks **bez ponownego parsowania**.

**2. Budujemy bazę wektorową (RAG).** Karty spraw zamieniamy na reprezentacje matematyczne
(„embeddingi"), które pozwalają szukać **po znaczeniu, a nie po słowach kluczowych** — zgłoszenie
„drukarka nie chce gadać z systemem" trafi do sprawy opisanej jako „brak komunikacji z terminalem
fiskalnym", mimo że nie mają wspólnego słowa. Do indeksu wpuszczamy tylko sprawy faktycznie
rozwiązane; duplikaty tego samego problemu są scalane, żeby nie zdominowały wyników.

**3. Generujemy propozycję odpowiedzi.** Nowe zgłoszenie przechodzi tę samą normalizację, system
znajduje 1–3 najbardziej podobne sprawy i na ich podstawie układa projekt odpowiedzi.

## Najciekawsze decyzje techniczne

**Polski model wyszukiwania PolDense.** Używamy nowego modelu embeddingowego od **OPI-PIB
(Ośrodek Przetwarzania Informacji — Państwowy Instytut Badawczy)**, przygotowanego specjalnie
pod język polski i osiągającego czołowe wyniki na polskim benchmarku PIRB. To istotne, bo modele
„uniwersalne" radzą sobie z polską odmianą i szykiem wyraźnie gorzej, a nasze dane to w całości
polska korespondencja z klientami. Model jest przy tym **mały** (kilkadziesiąt–kilkaset milionów
parametrów), więc działa lokalnie na jednej karcie graficznej, bez opłat za zapytanie i bez
wysyłania czegokolwiek na zewnątrz.

**System nigdy nie zmyśla danych.** Tam gdzie brakuje informacji, w odpowiedzi pojawia się
wypełniacz (`{IMIĘ}`, `{NR_URZĄDZENIA}`) zamiast wymyślonej wartości. Każda propozycja przychodzi
z listą źródeł, więc wdrożeniowiec widzi, skąd system to wziął, i może zweryfikować.

**System wie, kiedy nie wie.** Zamiast zawsze produkować odpowiedź, wynik jest kierowany jedną
z trzech ścieżek: (a) pewne dopasowanie → pełny projekt odpowiedzi; (b) niepewne lub sprzeczne
źródła → szablon diagnostyczny z pytaniami do klienta; (c) brak dopasowania → **żadnej propozycji
plus sygnał „nowy typ problemu"**. Ta trzecia ścieżka jest cenna sama w sobie — pokazuje, gdzie
w produkcie pojawiają się nowe kategorie awarii.

**Człowiek zawsze zatwierdza.** Produktem jest *propozycja* dla wdrożeniowca. Nie planujemy
automatycznej wysyłki do klienta.

## Problemy i ryzyka

**Jedno zgłoszenie, kilka problemów naraz.** Realne zgłoszenia rzadko są jednotematyczne —
klient przy okazji awarii drukarki dopisuje pytanie o fakturę i prośbę o zmianę uprawnień.
Naiwne podejście („jedno zgłoszenie = jedna karta sprawy") zlepia je w jeden opis, który nie
pasuje potem do żadnego z tych problemów z osobna, a jakość wyszukiwania spada po cichu — bez
błędu, po prostu gorszymi podpowiedziami. Rozwiązanie: **parser rozbija zgłoszenie na tyle kart
sprawy, ile realnie zawiera problemów**, wiążąc je wspólnym numerem zgłoszenia źródłowego.
Pociąga to za sobą decyzje, których nie da się odłożyć poza etap 2: jak parować problem
z odpowiadającym mu fragmentem rozwiązania i co zrobić, gdy nowe zgłoszenie też jest złożone
(prawdopodobnie: osobne wyszukiwanie na każdy wątek i złożenie jednej odpowiedzi z kilku źródeł).

## Plan prac

Prace podzielone są na osiem etapów, ułożonych tak, by **decyzje kosztowne zapadały po pomiarze,
a nie przed**:

1. **Fundament** — szkielet aplikacji i środowiska uruchomieniowego.
2. **Kontrakt karty sprawy** — ustalenie, jakie pola wyciągamy ze zgłoszenia. Na tej podstawie
   ręcznie parsujemy pierwszą partię, żeby zobaczyć realny wynik przed automatyzacją.
3. **Pomiar skuteczności wyszukiwania** — tu zapada ostateczny wybór modelu.
4. **Budowa indeksu** z kart spraw.
5. **Wyszukiwanie** — pierwsza działająca funkcja end-to-end.
6. **Generowanie propozycji odpowiedzi** — produkt docelowy w wersji minimalnej.
7. **Automatyczny import** nowych zgłoszeń pod realny format danych.
8. **Rozszerzenia** — wyszukiwanie po kodach błędów, interfejs użytkownika, zbieranie informacji
   zwrotnej od wdrożeniowców.