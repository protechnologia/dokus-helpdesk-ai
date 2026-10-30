<!-- Opis narzędzia odpowiedzi grafu `suggest_handoff` — czyta go MODEL razem ze schematem
     argumentów (schemat z `Proposal`, bez docstringów, przykładów i pól `FILLED_BY_GRAPH` —
     patrz respond_tool.py). Treść stroi się z promptem w p. 27.

     Układ jak w opisach narzędzi agenta: cztery sekcje, argumenty w tabelce, linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki. „Co zwraca" jest bez tabelki, bo narzędzie nic modelowi
     nie oddaje. Sekcji pilnuje test kontraktu grafów. Przykład w tabelce pokazuje układ wiadomości,
     a model może go przepisać — czy to robi, liczy pomiar w p. 27.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Oddaje wiadomość dla klienta o przekazaniu zgłoszenia do dalszych
prac po stronie serwisu.

# Jak wywoływać

| argument | typ    | przykłady | opis |
|----------|--------|-----------|------|
| text     | string | "Dzień dobry.\n\nPo aktualizacji nie działa podpis kwalifikowany, a certyfikat jest ważny.\n\nSprawę przekazujemy do dalszych prac po stronie serwisu.\n\nPozdrawiam." | Gotowa wiadomość dla klienta, w układzie z przykładu. |

# Co zwraca

Nic: wywołanie kończy sprawę. Odpowiedź, która łamie zasady niżej,
wraca jako błąd do poprawki.

# Zasady

- Wywołaj raz, jako jedyne wywołanie w turze.
