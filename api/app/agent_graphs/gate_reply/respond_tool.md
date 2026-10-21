<!-- Opis narzędzia odpowiedzi grafu `gate_reply` — czyta go MODEL razem ze schematem argumentów
     (schemat z `Verdict`, bez docstringów i przykładów — patrz respond_tool.py).

     Ten sam `Verdict` co w `gate_close`, ale pola znaczą tu co innego: `reasons` to złamane
     reguły wysyłki, nie braki w opisie. Dlatego każdy graf ma własny opis. Szkielet z p. 5;
     treść stroi się z promptem w p. 22.

     Układ jak w opisach narzędzi agenta: cztery sekcje, argumenty w tabelce, linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki. „Co zwraca" jest bez tabelki, bo narzędzie nic modelowi
     nie oddaje. Sekcji pilnuje test kontraktu grafów. Przykład w tabelce model może przepisać —
     czy to robi, liczy pomiar w p. 22.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Oddaje werdykt bramki wysyłki: czy wiadomość może wyjść do klienta,
a jeśli nie, to którą regułę łamie i co zmienić. Werdykt widzi
wdrożeniowiec, który wysyła wiadomość.

# Jak wywoływać

| argument | typ      | przykłady                                               | opis |
|----------|----------|---------------------------------------------------------|------|
| verdict  | string   | "pass", "block"                                         | `"pass"`, gdy wiadomość nie łamie żadnej reguły wysyłki; inaczej `"block"`. |
| reasons  | string[] | ["Prośba „proszę podać hasło” łamie regułę o hasłach."] | Po jednym zdaniu na każdą złamaną regułę, z fragmentem wiadomości, który ją łamie. |
| hint     | string   | "Usuń prośbę o hasło."                                  | Jedno–dwa zdania dla wdrożeniowca: co zmienić, żeby wiadomość mogła wyjść. |

# Co zwraca

Nic: wywołanie kończy ocenę. Werdykt, który łamie zasady niżej,
wraca jako błąd do poprawki.

# Zasady

- Wywołaj raz, po ocenie wiadomości, jako jedyne wywołanie w turze.
- Przy `"block"` pola `reasons` i `hint` są obowiązkowe.
- Przy `"pass"` zostaw `hint` pusty.
