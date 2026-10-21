<!-- Opis narzędzia odpowiedzi grafu `gate_close` — czyta go MODEL razem ze schematem argumentów
     (schemat z `Verdict`, bez docstringów i przykładów — patrz respond_tool.py).

     Znaczenie pól jest TU, nie w prompcie systemowym: model czyta je przy definicji narzędzia,
     którym je wypełnia. Prompt systemowy mówi tylko, że werdykt wydaje się tym narzędziem.
     Szkielet z p. 5; treść stroi się z promptem w p. 21.

     Układ jak w opisach narzędzi agenta: cztery sekcje, argumenty w tabelce, linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki. „Co zwraca" jest bez tabelki, bo narzędzie nic modelowi
     nie oddaje. Sekcji pilnuje test kontraktu grafów. Przykład w tabelce model może przepisać —
     czy to robi, liczy pomiar w p. 21.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Oddaje werdykt bramki zamknięcia: czy zgłoszenie można zamknąć,
a jeśli nie, to dlaczego i co dopisać. Werdykt widzi wdrożeniowiec,
który zamyka zgłoszenie.

# Jak wywoływać

| argument | typ      | przykłady                              | opis |
|----------|----------|----------------------------------------|------|
| verdict  | string   | "pass", "block"                        | `"pass"`, gdy zgłoszenie spełnia reguły zamknięcia; inaczej `"block"`. |
| reasons  | string[] | ["Nie widać, co zostało zrobione."]    | Uzasadnienia, po jednym zdaniu na każdą niespełnioną regułę. |
| hint     | string   | "Dopisz, co zmieniono w ustawieniach." | Jedno–dwa zdania dla wdrożeniowca: co dopisać, żeby zamknięcie przeszło. |

# Co zwraca

Nic: wywołanie kończy ocenę. Werdykt, który łamie zasady niżej,
wraca jako błąd do poprawki.

# Zasady

- Wywołaj raz, po ocenie zgłoszenia, jako jedyne wywołanie w turze.
- Przy `"block"` pola `reasons` i `hint` są obowiązkowe.
- Przy `"pass"` zostaw `hint` pusty.
