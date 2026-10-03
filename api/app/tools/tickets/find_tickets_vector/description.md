<!-- Opis narzędzia `find_tickets_vector` — czyta go MODEL razem ze schematem
     argumentów (`FindTicketsVectorQuery` bez docstringów), w każdym grafie,
     który ma to narzędzie na liście. Mówi, jak pytać narzędzie i co ono oddaje;
     po co wyniki w danej funkcji, mówi prompt grafu.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego trzeba
     przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Szuka w bazie historycznych zgłoszeń spraw podobnych do opisanego problemu, od
najbardziej podobnej. Zwraca karty zgłoszeń, nie oryginalne wątki: każda sprawa
jest streszczona w polach `problem`, `symptoms`, `cause`, `solution` i kilku
pomocniczych. Dosłownych sformułowań klienta i części szczegółów może w karcie
nie być, a `brak` w polu znaczy, że tego nie ustalono.

Pytaj w kształcie karty, nie surowym mailem — bez powitań, podpisów i historii
wątku:

- `problem` — jednym-dwoma zdaniami, czego dotyczy kłopot;
- `symptoms` — co widzi użytkownik, z komunikatem błędu, jeśli jest.

Gdy zgłoszenie opisuje kilka różnych objawów, szukaj osobno dla każdego.
