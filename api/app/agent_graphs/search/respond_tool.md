<!-- Opis narzędzia odpowiedzi grafu `search` — czyta go MODEL razem ze schematem argumentów
     (schemat z `SearchNotes`, bez docstringów i przykładów — patrz respond_tool.py). Kształt
     uwag opisuje prompt systemowy (wzór czterech sekcji), tu tylko pole. Listy źródeł model nie
     podaje: powstaje z odczytów i z cytowań przyczyny (zasada 9). Treść stroi się z promptem
     w p. 23.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Kończy rozpoznanie i oddaje uwagi dla wdrożeniowca. Wywołaj je, gdy kolejne wyszukanie nic nowego
nie dodaje — jako jedyne wywołanie w turze. Listy źródeł nie podajesz: wdrożeniowiec dostanie to,
co odczytałeś, i fragmenty kodu zacytowane jako przyczyna.

- `internal_notes` — uwagi dla wdrożeniowca w lekkim Markdownie, w czterech sekcjach ze wzoru
  z instrukcji (Zgłoszenia historyczne, Instrukcje i dokumentacja, Kod aplikacji, Nie znaleziono),
  po polsku; nigdy puste.
