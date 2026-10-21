<!-- Opis narzędzia odpowiedzi grafu `suggest_handoff` — czyta go MODEL razem ze schematem
     argumentów (schemat z `Proposal`, bez docstringów i przykładów — patrz respond_tool.py).
     Szkielet z p. 5; treść stroi się z promptem w p. 27.

     Układ jak w opisach narzędzi agenta: cztery sekcje, argumenty w tabelce, linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki. „Co zwraca" jest bez tabelki, bo narzędzie nic modelowi
     nie oddaje. Sekcji pilnuje test kontraktu grafów. Przykład w tabelce model może przepisać —
     czy to robi, liczy pomiar w p. 27.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Oddaje tekst informacji o przekazaniu zgłoszenia do dalszych prac
po stronie serwisu i osobno uwagi dla wdrożeniowca.

# Jak wywoływać

| argument       | typ    | przykłady                                            | opis |
|----------------|--------|------------------------------------------------------|------|
| text           | string | "Dzień dobry, zgłoszenie przekazaliśmy do analizy…"  | Gotowa treść dla klienta po polsku, bez wstępu od siebie. |
| internal_notes | string | "Serwis potrzebuje logów kolejki z dnia zgłoszenia." | Uwagi dla wdrożeniowca, których klient nie dostaje; pusty napis, gdy uwag nie masz. |

# Co zwraca

Nic: wywołanie kończy sprawę. Odpowiedź, która łamie zasady niżej,
wraca jako błąd do poprawki.

# Zasady

- Wywołaj raz, jako jedyne wywołanie w turze.
