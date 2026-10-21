<!-- Opis narzędzia odpowiedzi grafu `polish` — czyta go MODEL razem ze schematem argumentów
     (schemat z `PolishedText`, bez docstringów i przykładów — patrz respond_tool.py).
     Szkielet z p. 5; treść stroi się z promptem w p. 28.

     Układ jak w opisach narzędzi agenta: cztery sekcje, argumenty w tabelce, linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki. „Co zwraca" jest bez tabelki, bo narzędzie nic modelowi
     nie oddaje. Sekcji pilnuje test kontraktu grafów. Przykład w tabelce model może przepisać —
     czy to robi, liczy pomiar w p. 28.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Oddaje poprawiony tekst: ten sam sens co w notatkach wdrożeniowca,
w poprawnej formie. Tekst trafia do wdrożeniowca, który wysyła go
klientowi.

# Jak wywoływać

| argument | typ    | przykłady                              | opis |
|----------|--------|----------------------------------------|------|
| text     | string | "Dzień dobry, przesyłki z e-Doręczeń…" | Ten sam sens co w notatkach, w poprawnej formie; gotowy do wysłania po polsku. |

# Co zwraca

Nic: wywołanie kończy poprawianie. Odpowiedź, która łamie zasady
niżej, wraca jako błąd do poprawki.

# Zasady

- Wywołaj raz, jako jedyne wywołanie w turze.
