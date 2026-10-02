<!-- Opis narzędzia odpowiedzi grafu `gate_reply` — czyta go MODEL razem ze schematem argumentów
     (schemat z `Verdict`, bez docstringów i przykładów — patrz respond_tool.py).

     Ten sam `Verdict` co w `gate_close`, ale pola znaczą tu co innego: `reasons` to złamane
     reguły wysyłki, nie braki w opisie. Dlatego każdy graf ma własny opis. Szkielet z p. 5;
     treść stroi się z promptem w p. 22.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Wydaje werdykt bramki wysyłki. Wywołaj je raz, po ocenie wiadomości, jako jedyne wywołanie
w turze.

- `verdict` — `"pass"`, gdy wiadomość nie łamie żadnej reguły wysyłki; inaczej `"block"`.
- `reasons` — po jednym zdaniu na każdą złamaną regułę, z fragmentem wiadomości, który ją łamie.
- `missing` — krótkie nazwy tego, czego wiadomości brakuje, jeśli reguła czegoś wymaga.
- `hint` — jedno-dwa zdania dla wdrożeniowca: co zmienić, żeby wiadomość mogła wyjść.

Przy `"block"` pola `reasons` i `hint` są obowiązkowe. Przy `"pass"` zostaw `missing` i `hint`
puste.
