<!-- Opis narzędzia odpowiedzi grafu `gate_close` — czyta go MODEL razem ze schematem argumentów
     (schemat z `Verdict`, bez docstringów i przykładów — patrz respond_tool.py).

     Znaczenie pól jest TU, nie w prompcie systemowym: model czyta je przy definicji narzędzia,
     którym je wypełnia. Prompt systemowy mówi tylko, że werdykt wydaje się tym narzędziem.
     Szkielet z p. 5; treść stroi się z promptem w p. 21.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Wydaje werdykt bramki zamknięcia. Wywołaj je raz, po ocenie zgłoszenia, jako jedyne wywołanie
w turze.

- `verdict` — `"pass"`, gdy zgłoszenie spełnia reguły zamknięcia; inaczej `"block"`.
- `reasons` — uzasadnienia, po jednym zdaniu na każdą niespełnioną regułę.
- `missing` — krótkie nazwy tego, czego brakuje w treści zgłoszenia.
- `hint` — jedno-dwa zdania dla wdrożeniowca: co dopisać, żeby zamknięcie przeszło.

Przy `"block"` pola `reasons` i `hint` są obowiązkowe. Przy `"pass"` zostaw `missing` i `hint`
puste.
