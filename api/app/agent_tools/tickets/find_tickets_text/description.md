<!-- Opis narzędzia `find_tickets_text` — czyta go MODEL razem ze
     schematem argumentów (`FindTicketsTextQuery` bez docstringów),
     w każdym grafie, który ma to narzędzie na liście. Mówi, jak pytać
     narzędzie i co ono oddaje; po co wyniki w danej funkcji, mówi
     prompt grafu. Szkielet; narzędzie właściwe w p. 53.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty i pola wyniku w tabelkach, linie do 70 znaków —
     dłuższe bywają tylko wiersze tabelki argumentów.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Szuka historycznych zgłoszeń w bazie pełnotekstowej: po dosłownym
brzmieniu i po słowach kluczowych, nie po znaczeniu — w oryginalnych
wątkach, nie w kartach, czyli streszczeniach zgłoszeń. Użyj, gdy
zgłoszenie niesie coś, co da się znaleźć słowo w słowo.

# Jak wywoływać

| argument | typ   | co podać                    | przykład          | opis |
|----------|-------|-----------------------------|-------------------|------|
| exact    | tekst | fraza wyszukiwana dosłownie | "SQLSTATE[23000]" | Bez odmiany, w podanej kolejności, bez względu na wielkość liter. Nadaje się do kodu błędu, sygnatury, fragmentu komunikatu z ekranu. Przepisz ją bez zmian; co najmniej trzy znaki. |
| words    | tekst | słowa kluczowe              | "załącznik limit" | Wyszukiwane w dowolnej odmianie i kolejności („załącznik" znajdzie „załączników"); zgłoszenie musi zawierać wszystkie. |

Podaj co najmniej jedno pole. Każde szuka osobno, a wyniki się
sumują: zgłoszenie wraca, gdy zawiera frazę z `exact` albo wszystkie
słowa z `words`.

# Co zwraca

JSON z samymi numerami zgłoszeń, bez treści:

| pole                 | co zawiera                                 |
|----------------------|--------------------------------------------|
| tickets              | znalezione zgłoszenia                      |
| tickets[].ticket_id  | numer zgłoszenia                           |
| tickets[].matched_by | czym znalezione: `exact` albo `words`      |
| omitted_over_limit   | ile pasujących zgłoszeń ponad limit wyniku |

# Zasady

- Jedno wywołanie to jedna fraza: kolejną frazę sprawdź osobnym
  wywołaniem.
- Karty, czyli streszczenia zgłoszeń, odczytasz narzędziem
  `read_tickets_card`.
- Oryginalne wątki odczytasz narzędziem `read_tickets_thread`.
- Ten sam komunikat miewa różne przyczyny: trafienie mówi, że taki
  objaw już był, a nie co go wywołało.
- Wynik ma limit długości: zgłoszenia pasujące ponad niego są tylko
  policzone w `omitted_over_limit`. Wartość większa od zera znaczy,
  że zapytanie było zbyt ogólne.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
