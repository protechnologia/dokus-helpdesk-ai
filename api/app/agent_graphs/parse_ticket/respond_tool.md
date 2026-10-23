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

     UWAGA: FRAZY UCIECZKOWE („brak", „nie dotyczy") SĄ KONTRAKTEM FILTRU JAKOŚCI.
     Filtr indeksacji (frazy w core_service/normalizer_ticket_sentinel.py) rozpoznaje rekord bez wiedzy po tym,
     że `solution` niesie frazę ucieczkową i niewiele poza nią — nie po stylu wypowiedzi modelu. To
     jedyny powód, dla którego filtr przeżywa podmianę modelu. Zmiana tych fraz albo instrukcji,
     KIEDY je stosować, jest więc zmianą filtru, choćby nie tknęła jego kodu. Po takiej edycji
     uruchom test na korpusie referencyjnym
     (tests/evaluation/test_api_core_service_filter_ticket_quality_corpus.py).

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
| solution          | string   | "Włączono usługę generowania grafik…", "brak"                    | Co rozstrzygnęło sprawę, razem z ograniczeniami i skutkami ubocznymi. |
| resolution        | string   | "naprawione", "brak"                                             | Jedna nazwa ze słownika rozstrzygnięć podanego w danych. |
| questions_summary | string   | "Pytano o wersję sterownika drukarki…", "brak"                   | Czego prowadzący sprawę nie wiedział i o co dopytywał. |

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
  w wątku, bez domysłów (np. „prawdopodobnie…") i bez wykluczonych
  przyczyn.
- Wypełniając pole `solution`, przenieś z wątku komplet zastrzeżeń
  (np. skutki uboczne, kogo dotyczy zmiana, od kiedy działa, czy
  obejmuje dawne przypadki) i to, kto wykonał krok: użytkownik czy
  dostawca. Odmowa też jest rozwiązaniem, a obietnica (np. „zajmiemy
  się", „przekażemy do działu technicznego") nie.
- Wypełniając pole `resolution`, użyj wartości oznaczającej brak
  rozstrzygnięcia, jeśli wątek nie pozwala rozstrzygnąć.
- Wypełniając pole `questions_summary`, bierz wyłącznie pytania
  osoby obsługującej, bez pytań zgłaszającego (nawet technicznych)
  i bez proceduralnych (np. „czy problem nadal występuje?"). Zachowaj
  konkrety: „Pytano o rozdzielczość ekranu i profil skanowania
  w NAPS2", a nie „Pytano o konfigurację stanowiska".
