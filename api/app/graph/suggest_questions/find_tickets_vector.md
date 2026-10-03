<!-- Opis narzędzia `find_tickets_vector` w grafie `suggest_questions` — czyta go MODEL razem ze
     schematem argumentów (`FindTicketsVectorQuery` bez docstringów). Opis jest per graf,
     bo ten sam kod narzędzia służy różnym celom. Treść i pomiar trafności zapytań agenta
     w p. 25.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Szuka w bazie historycznych zgłoszeń spraw podobnych do opisanego problemu. Zwraca zgłoszenia
z przyczyną i rozwiązaniem, od najbardziej podobnego.

Pytaj w kształcie bazy, nie surowym mailem — bez powitań, podpisów i historii wątku:

- `problem` — jednym-dwoma zdaniami, czego dotyczy kłopot;
- `symptoms` — co widzi użytkownik, z komunikatem błędu, jeśli jest.

Trafienia służą do PYTAŃ: zbierz przyczyny ze wszystkich, bo rozróżniasz je pytaniami.
