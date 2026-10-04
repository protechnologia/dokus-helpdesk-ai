<!-- Opis narzędzia `find_tickets_vector` — czyta go MODEL razem ze schematem
     argumentów (`FindTicketsVectorQuery` bez docstringów), w każdym grafie,
     który ma to narzędzie na liście. Mówi, jak pytać narzędzie i co ono oddaje;
     po co wyniki w danej funkcji, mówi prompt grafu.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego trzeba
     przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Szuka w bazie historycznych zgłoszeń spraw podobnych do opisanego problemu, od
najbardziej podobnej. Zwraca same numery zgłoszeń z podobieństwem (`score`), bez
treści. Treść odczytasz osobno: karty narzędziem `read_tickets_card`, oryginalne
wątki narzędziem `read_tickets_thread`.

`score` porównuje trafienia w jednym wyniku; nie mówi, czy rozwiązanie pasuje.
Sprawy o tym samym objawie mają tu różne przyczyny, więc przeczytaj karty
wszystkich zwróconych numerów, nie tylko pierwszego. Gdy wszystkie wyniki są
słabe albo `dropped_below_threshold` jest większe od zera, spróbuj innego opisu.

Pytaj w kształcie karty, nie przepisuj zgłoszenia wprost — bez powitań,
podpisów i historii wątku:

- `problem` — jednym-dwoma zdaniami, czego dotyczy kłopot;
- `symptoms` — co widzi użytkownik, z komunikatem błędu, jeśli jest.

Gdy zgłoszenie opisuje kilka różnych objawów, szukaj osobno dla każdego.

Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu narzędzie
zwraca błąd zamiast wyniku.
