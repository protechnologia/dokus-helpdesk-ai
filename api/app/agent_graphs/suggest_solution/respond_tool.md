<!-- Opis narzędzia odpowiedzi grafu `suggest_solution` — czyta go MODEL razem ze schematem
     argumentów (schemat z `Proposal`, bez docstringów i przykładów — patrz respond_tool.py).
     Kształt samej treści opisuje prompt systemowy (wzór odpowiedzi), tu tylko pole. Szkielet
     z p. 5; treść stroi się z promptem w p. 26.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Oddaje treść rozwiązania dla klienta. Wywołaj je raz, po wyszukaniu, jako jedyne wywołanie
w turze.

- `text` — treść w kształcie ze wzoru z instrukcji, po polsku, bez wstępu.
