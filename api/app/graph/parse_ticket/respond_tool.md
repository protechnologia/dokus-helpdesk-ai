<!-- Opis narzędzia odpowiedzi grafu `parse_ticket` — czyta go MODEL razem ze schematem argumentów
     (ParsedTicket bez docstringów i bez pól, które wypełnia graf: ticket_id, date,
     resolution_vocabulary_version — patrz respond_tool.py). Część KONTRAKTU ARTEFAKTU, jak
     prompt_system.md (zasada 7). Sekcję „Pola karty" test-strażnik czyta osobno (`field_rules()`),
     żeby skasowany opis pola nie przechodził dzięki nazwie w przykładach.

     UWAGA: FRAZY UCIECZKOWE („brak", „nie dotyczy") SĄ KONTRAKTEM FILTRU JAKOŚCI.
     Filtr indeksacji (service/filter_ticket_quality_rules.py) rozpoznaje rekord bez wiedzy po tym,
     że `solution` niesie frazę ucieczkową i niewiele poza nią — nie po stylu wypowiedzi modelu. To
     jedyny powód, dla którego filtr przeżywa podmianę modelu. Zmiana tych fraz albo instrukcji,
     KIEDY je stosować, jest więc zmianą filtru, choćby nie tknęła jego kodu. Po takiej edycji
     uruchom test na korpusie referencyjnym
     (tests/unit/test_api_service_filter_ticket_quality_corpus.py).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Oddaje kartę zgłoszenia. Wywołaj je raz, po przeczytaniu całego wątku, jako jedyne wywołanie
w turze.

## Pola karty

`component` — czego sprawa dotyczy. Jedna wartość. Nie zgaduj po nazwie modułu — zgłoszenie
potrafi dotyczyć usługi zewnętrznej albo cudzego oprogramowania. Dla naszego systemu wpisz
„główna aplikacja".

`problem` — 1–2 zdania o tym, CO nie działa. Tak, żeby dało się dopasować inne zgłoszenie
o tym samym kłopocie.

`symptoms` — co widzi użytkownik: komunikaty, moment wystąpienia, czynność przed błędem.
Gdy zgłoszenie nie opisuje awarii, tylko pyta o działanie systemu — „nie dotyczy".

`error_codes` — lista kodów i sygnatur. Zapisz OBA, jeśli oba są w wątku: kod z ekranu ORAZ kod
z logów. Normalizuj — obetnij ścieżki instalacji, nazwy serwerów i wartości kluczy. Brak kodów
to pusta lista.

`cause` — ustalona przyczyna. Nie wpisuj hipotezy, którą później obalono. Brak ustalenia — „brak".

`solution` — co rozstrzygnęło sprawę. Obowiązkowo:

- KOMPLET ZASTRZEŻEŃ: skutek uboczny; zasięg zmiany („ustawienie globalne"); zakres czasowy
  („dla zaległych nie ma drogi"); kompletność naprawy wstecznej. Pominięcie zastrzeżenia
  zamienia odpowiedź w jej przeciwieństwo.
- KTO wykonuje krok — użytkownik u siebie czy dostawca.
- ODMOWA też jest rozwiązaniem („nie zostanie zrealizowane, ponieważ…") i bywa najcenniejsza,
  bo mówi, czego NIE robić.

Bez rozstrzygnięcia — „brak". Obietnice („zajmiemy się", „przekażemy") to nie rozwiązanie.

`resolution` — dokładnie jedna nazwa ze słownika rozstrzygnięć podanego w danych. Jeśli wątek
nie pozwala rozstrzygnąć, użyj wartości oznaczającej brak rozstrzygnięcia.

`questions_summary` — czego prowadzący sprawę NIE wiedział i o co dopytywał. Liczą się WYŁĄCZNIE
pytania osoby obsługującej; pytania zgłaszającego POMIŃ, nawet techniczne. POMIŃ też pytania
proceduralne („czy problem nadal występuje?", „czy możemy zamknąć?"). MUSI zachować konkrety:

- „Pytano o konfigurację stanowiska" jest bezwartościowe.
- „Pytano o rozdzielczość ekranu i profil skanowania w NAPS2" niesie wiedzę.

Gdy nikt o nic nie dopytywał — „brak". To normalny, częsty stan.

## Przykłady

Dwa przykłady pokazują sam KSZTAŁT argumentów. Nie kopiuj z nich treści ani stylu — zapisuj to,
co jest w konkretnym wątku.

Wątek zakończony rozstrzygnięciem:

```json
{
  "component": "usługa kurierska",
  "problem": "Etykiety nadania generują się bez kodu kreskowego.",
  "symptoms": "Po zatwierdzeniu przesyłki plik PDF ma pustą ramkę w miejscu kodu.",
  "error_codes": ["LBL-503"],
  "cause": "Wyłączona usługa generowania grafik po stronie serwera wydruków.",
  "solution": "Włączono usługę generowania grafik i przegenerowano etykiety. Wykonuje dostawca. Zastrzeżenie: przegenerowane zostały wyłącznie przesyłki z ostatnich 7 dni, starsze etykiety pozostają bez kodu.",
  "resolution": "naprawione",
  "questions_summary": "Pytano o wersję sterownika drukarki i o to, czy problem dotyczy wydruku seryjnego, czy pojedynczej etykiety."
}
```

Wątek bez rozstrzygnięcia — to normalny, częsty przypadek, nie błąd:

```json
{
  "component": "główna aplikacja",
  "problem": "Import listy kontrahentów przerywa się w połowie pliku.",
  "symptoms": "Proces zatrzymuje się po kilkuset wierszach, bez komunikatu błędu.",
  "error_codes": [],
  "cause": "brak",
  "solution": "brak",
  "resolution": "brak",
  "questions_summary": "brak"
}
```
