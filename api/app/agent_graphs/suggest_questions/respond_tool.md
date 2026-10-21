<!-- Opis narzędzia odpowiedzi grafu `suggest_questions` — czyta go MODEL razem ze schematem
     argumentów (schemat z `QuestionsAnswer`, bez docstringów i przykładów — patrz
     respond_tool.py).
     Kształt listy i notatek opisuje prompt systemowy (wzór odpowiedzi), tu tylko pola. Szkielet
     z p. 5; treść stroi się z promptem w p. 25.

     Układ jak w opisach narzędzi agenta: cztery sekcje, argumenty w tabelce, linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki. „Co zwraca" jest bez tabelki, bo narzędzie nic modelowi
     nie oddaje. Sekcji pilnuje test kontraktu grafów, a wzmianki o `null` — test grafu
     `suggest_questions`. Przykład w tabelce model może przepisać — czy to robi, liczy pomiar
     w p. 25.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Oddaje listę pytań, które wdrożeniowiec zada klientowi, i osobno
notatki do tych pytań.

# Jak wywoływać

| argument       | typ              | przykłady                                       | opis |
|----------------|------------------|-------------------------------------------------|------|
| text           | string albo null | "1. Od kiedy nie przychodzą przesyłki? …", null | Ponumerowana lista pytań w kształcie z instrukcji, po polsku, bez wstępu; `null`, gdy fakty ze zgłoszenia rozstrzygają sprawę i pytań nie trzeba. |
| internal_notes | string           | "Ad. 1. odcina zacięcie kolejki (zgł. 41002)"   | Notatki dla wdrożeniowca do pytań, których klient nie dostaje; pusty napis, gdy notatek nie masz. Przy `text` równym `null` obowiązkowe: dlaczego pytań już nie trzeba. |

# Co zwraca

Nic: wywołanie kończy sprawę. Odpowiedź, która łamie zasady niżej,
wraca jako błąd do poprawki.

# Zasady

- Wywołaj raz, po wyszukaniu, jako jedyne wywołanie w turze.
