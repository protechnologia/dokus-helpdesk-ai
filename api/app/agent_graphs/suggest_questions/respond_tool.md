<!-- Opis narzędzia odpowiedzi grafu `suggest_questions` — czyta go MODEL razem ze schematem
     argumentów (schemat z `Proposal`, bez docstringów i przykładów — patrz respond_tool.py).
     Kształt listy i notatek opisuje prompt systemowy (wzór odpowiedzi), tu tylko pola. Szkielet
     z p. 5; treść stroi się z promptem w p. 25.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Oddaje listę pytań, które wdrożeniowiec zada klientowi, i osobno notatki do tych pytań. Wywołaj
je raz, po wyszukaniu, jako jedyne wywołanie w turze.

- `text` — ponumerowana lista pytań w kształcie z instrukcji, po polsku, bez wstępu.
- `internal_notes` — notatki dla wdrożeniowca do pytań, których klient nie dostaje; pusty napis,
  gdy notatek nie masz.
