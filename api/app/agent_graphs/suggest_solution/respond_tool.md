<!-- Opis narzędzia odpowiedzi grafu `suggest_solution` — czyta go MODEL razem ze schematem
     argumentów (schemat z `Proposal`, bez docstringów i przykładów — patrz respond_tool.py).
     Kształt treści i uwag opisuje prompt systemowy (wzory odpowiedzi), tu tylko pola. Szkielet
     z p. 5; treść stroi się z promptem w p. 26.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Oddaje treść rozwiązania dla klienta i osobno uwagi dla wdrożeniowca. Wywołaj je raz, po
wyszukaniu, jako jedyne wywołanie w turze.

- `text` — treść dla klienta w kształcie ze wzoru z instrukcji, po polsku, bez wstępu.
- `internal_notes` — uwagi dla wdrożeniowca, których klient nie dostaje; pusty napis, gdy uwag
  nie masz.
