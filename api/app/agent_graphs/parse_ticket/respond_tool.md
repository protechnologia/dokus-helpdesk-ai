<!-- Opis narzędzia odpowiedzi grafu `parse_ticket` — czyta go MODEL razem ze schematem argumentów
     (ParsedTicket bez docstringów i bez pól, które wypełnia graf: ticket_id, date,
     resolution_vocabulary_version — patrz respond_tool.py). Część KONTRAKTU ARTEFAKTU, jak
     prompt_system.md (zasada 7).

     Układ jak w opisach narzędzi agenta (od 2026-10-23, p. 24): cztery sekcje, argumenty
     w tabelce, linie do 70 znaków; dłuższe bywają tylko wiersze tabelki.
     Reguły pól są za długie na komórkę tabelki, więc tabelka mówi o polu jedno zdanie, a pełne
     reguły stoją w „Zasadach", po punkcie na pole, w postaci „Wypełniając pole `pole`, …". Test-strażnik czyta
     je stamtąd (`field_rules()`), żeby skasowana reguła pola nie przechodziła dzięki nazwie
     w tabelce. Przykładów całej karty w JSON-ie nie ma (od 2026-10-23): kształt daje schemat,
     wartości każdego pola tabelka, a to, że pól nie wypełnia się na siłę, gdy wątek niewiele
     ustalił, mówi jedna z zasad.

     UWAGA: POLE `useful` JEST KONTRAKTEM FILTRU JAKOŚCI (od 2026-10-23). Filtr indeksacji
     (reguła `not_useful` w core_service/filter_ticket_quality_rules.py) odrzuca kartę, którą model
     ocenił jako nieprzydatną. Zmiana reguły tego pola albo przykładów, co jest wiedzą, jest więc
     zmianą filtru, choćby nie tknęła jego kodu. Po takiej edycji przelicz test na korpusie
     odniesienia (tests/evaluation/test_api_core_service_filter_ticket_quality_corpus.py), a karty
     odniesienia sparsuj od nowa (scripts/parse_golden_tickets.py).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Oddaje kartę zgłoszenia: treść wątku zapisaną w stałych polach.
Z kart powstaje baza wiedzy, w której szuka się spraw podobnych
do nowego zgłoszenia.

# Jak wywoływać

| argument          | typ      | przykłady                                                        | opis |
|-------------------|----------|------------------------------------------------------------------|------|
| component         | string   | "główna aplikacja", "ePUAP", "e-Doręczenia"                      | Czego sprawa dotyczy, jedna wartość. |
| problem           | string   | "Import listy kontrahentów przerywa się w połowie pliku."        | 1–2 zdania o tym, co nie działa albo o co pyta zgłaszający. |
| symptoms          | string   | "Plik PDF ma pustą ramkę w miejscu kodu.", "brak", "nie dotyczy" | Objawy problemu: komunikaty, moment wystąpienia, czynność przed błędem. |
| error_codes       | string[] | ["LBL-503"], []                                                  | Kody i sygnatury błędów z wątku. |
| cause             | string   | "Wyłączona usługa generowania grafik…", "brak", "nie dotyczy"    | Ustalona przyczyna. |
| excluded_causes   | string[] | ["Brak miejsca na dysku"], []                                    | Przyczyny, które wątek sprawdził i wykluczył. |
| solution          | string   | "Włączono usługę generowania grafik…", "brak"                    | Co rozstrzygnęło sprawę, razem z ograniczeniami i skutkami ubocznymi. |
| resolution        | string   | "naprawione", "brak"                                             | Jedna nazwa ze słownika rozstrzygnięć podanego w danych. |
| questions_summary | string   | "Pytano o wersję sterownika drukarki…", "brak"                   | Czego prowadzący sprawę nie wiedział i o co dopytywał. |
| useful            | boolean  | true, false                                                      | Czy karta przyda się przy innej sprawie. |
| useful_reason     | string   | "Wątek kończy się zapowiedzią poprawki, bez rozwiązania."        | Dlaczego karta przyda się albo nie. |

# Co zwraca

Nic: wywołanie kończy sprawę. Karta z pustym polem albo
z rozstrzygnięciem spoza słownika wraca jako błąd do poprawki.

# Zasady

- Wywołaj raz, po przeczytaniu całego wątku, jako jedyne wywołanie
  w turze.
- Wartości „brak" i „nie dotyczy" to dwa różne wyjścia: „brak", gdy
  pole dotyczy sprawy, ale wątek tego nie ustalił; „nie dotyczy", gdy
  pole nie pasuje do tego rodzaju zgłoszenia.
- Wątki często niosą mało informacji albo informacje nieprzydatne
  i nie pozwalają ustalić przyczyny ani rozwiązania. To normalne:
  nie wypełniaj wtedy pól na siłę, wpisz „brak".
- Wypełniając pole `component`, oceniaj po treści, nie po nazwie
  modułu. Gdy sprawa dotyczy aplikacji, którą obsługuje ten
  helpdesk, wpisz „główna aplikacja"; gdy usługi zewnętrznej albo
  cudzego oprogramowania, wpisz jego nazwę.
- Wypełniając pole `problem`, pisz tak, żeby dało się po nim znaleźć
  inne zgłoszenia z tym samym problemem.
- Wypełniając pole `symptoms`, wpisz „nie dotyczy", gdy zgłoszenie
  nie opisuje awarii, tylko pyta o działanie systemu.
- Wypełniając pole `error_codes`, zapisz wszystkie kody z wątku,
  z ekranu i z logów.
- Wypełniając pole `cause`, wpisz tylko przyczynę potwierdzoną
  w wątku, bez domysłów (np. „prawdopodobnie…").
- Wypełniając pole `excluded_causes`, wpisz tylko przyczyny, które
  wątek sprawdził i wykluczył, nie domysły.
- Wypełniając pole `solution`, przenieś z wątku komplet zastrzeżeń
  (np. skutki uboczne, kogo dotyczy zmiana, od kiedy działa, czy
  obejmuje dawne przypadki) i to, kto wykonał krok: użytkownik czy
  dostawca. Rozwiązaniem jest też wyjaśnienie, jak działa system,
  i naprawa po stronie dostawcy, także bez potwierdzenia klienta.
  Odmowa też jest rozwiązaniem, a obietnica (np. „zajmiemy się",
  „przekażemy do działu technicznego") nie.
- Wypełniając pole `resolution`, użyj wartości oznaczającej brak
  rozstrzygnięcia, jeśli wątek nie pozwala rozstrzygnąć.
- Wypełniając pole `questions_summary`, bierz wyłącznie pytania
  osoby obsługującej, bez pytań zgłaszającego (nawet technicznych)
  i bez proceduralnych (np. „czy problem nadal występuje?"). Zachowaj
  konkrety: „Pytano o rozdzielczość ekranu i profil skanowania
  w NAPS2", a nie „Pytano o konfigurację stanowiska".
- Wypełniając pole `useful`, oceń, czy karta przyda się przy innej
  sprawie: niesie przyczynę albo rozwiązanie, które przeniesie się na
  inną instalację. Przyda się też, gdy wątek wyjaśnia, jak działa
  system, kiedy występuje błąd albo że operacja mimo komunikatu się
  powiodła. Nie przyda się, gdy wątek tego nie niesie (np.
  formułka zamykająca, „omówione telefonicznie", „instrukcja
  w załączeniu", odesłanie do innego zgłoszenia, zapowiedź poprawki)
  albo nie jest zgłoszeniem (np. powiadomienie o aktualizacji).
- Wypełniając pole `useful_reason`, podaj jednym zdaniem, co w wątku
  przesądziło o ocenie.
