<!-- Opis narzędzia `find_tickets_vector` w grafie `suggest_solution` — czyta go MODEL razem ze schematem
     argumentów (`FindTicketsVectorQuery` bez docstringów). Opis jest per graf, bo ten sam kod narzędzia
     służy różnym celom. Szkielet z p. 5; treść w p. 26, trafność zapytań agenta w p. 23.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Szuka w bazie historycznych zgłoszeń spraw podobnych do opisanego problemu. Zwraca zgłoszenia
z przyczyną i rozwiązaniem, od najbardziej podobnego.

Pytaj w kształcie bazy, nie surowym mailem — bez powitań, podpisów i historii wątku:

- `problem` — jednym-dwoma zdaniami, czego dotyczy kłopot;
- `symptoms` — co widzi użytkownik, z komunikatem błędu, jeśli jest.

Trafienia są JEDYNYM źródłem faktów rozwiązania — czego w nich nie ma, tego nie piszesz.
