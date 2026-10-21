<!-- Opis narzędzia odpowiedzi grafu `suggest_solution` — czyta go MODEL razem ze schematem
     argumentów (schemat z `Proposal`, bez docstringów i przykładów — patrz respond_tool.py).
     Kształt treści i uwag opisuje prompt systemowy (wzory odpowiedzi), tu tylko pola. Szkielet
     z p. 5; treść stroi się z promptem w p. 26.

     Układ jak w opisach narzędzi agenta: cztery sekcje, argumenty w tabelce, linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki. „Co zwraca" jest bez tabelki, bo narzędzie nic modelowi
     nie oddaje. Sekcji pilnuje test kontraktu grafów. Przykład w tabelce model może przepisać —
     czy to robi, liczy pomiar w p. 26.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Oddaje treść rozwiązania dla klienta i osobno uwagi dla
wdrożeniowca.

# Jak wywoływać

| argument       | typ    | przykłady                                      | opis |
|----------------|--------|------------------------------------------------|------|
| text           | string | "Proszę w ustawieniach kancelarii włączyć…"    | Treść dla klienta w kształcie ze wzoru z instrukcji, po polsku, bez wstępu. |
| internal_notes | string | "Przyczyna jak w zgł. 41002: zacięta kolejka." | Uwagi dla wdrożeniowca, których klient nie dostaje; pusty napis, gdy uwag nie masz. |

# Co zwraca

Nic: wywołanie kończy sprawę. Odpowiedź, która łamie zasady niżej,
wraca jako błąd do poprawki.

# Zasady

- Wywołaj raz, po wyszukaniu, jako jedyne wywołanie w turze.
