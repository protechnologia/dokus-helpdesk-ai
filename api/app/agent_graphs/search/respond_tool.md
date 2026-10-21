<!-- Opis narzędzia odpowiedzi grafu `search` — czyta go MODEL razem ze schematem argumentów
     (schemat z `SearchNotes`, bez docstringów i przykładów — patrz respond_tool.py). Kształt
     uwag opisuje prompt systemowy (wzór czterech sekcji), tu tylko pole. Listy źródeł model nie
     podaje: powstaje z odczytów i z cytowań przyczyny (zasada 9). Treść stroi się z promptem
     w p. 23.

     Układ jak w opisach narzędzi agenta: cztery sekcje, argumenty w tabelce, linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki. „Co zwraca" jest bez tabelki, bo narzędzie nic modelowi
     nie oddaje. Sekcji pilnuje test kontraktu grafów, a nawiasu z nazwami czterech sekcji uwag —
     test grafu `search`. Przykład w tabelce model może przepisać — czy to robi, liczy pomiar
     w p. 23.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Kończy rozpoznanie i oddaje uwagi dla wdrożeniowca: co znalazłeś
w zgłoszeniach, instrukcjach i kodzie aplikacji i czego nie
znalazłeś.

# Jak wywoływać

| argument       | typ    | przykłady                        | opis |
|----------------|--------|----------------------------------|------|
| internal_notes | string | "## Zgłoszenia historyczne\n- …" | Uwagi dla wdrożeniowca w lekkim Markdownie, w czterech sekcjach ze wzoru z instrukcji (Zgłoszenia historyczne, Instrukcje i dokumentacja, Kod aplikacji, Nie znaleziono), po polsku; nigdy puste. |

# Co zwraca

Nic: wywołanie kończy rozpoznanie. Odpowiedź, która łamie zasady
niżej, wraca jako błąd do poprawki.

# Zasady

- Wywołaj, gdy kolejne wyszukanie nic nowego nie dodaje — jako
  jedyne wywołanie w turze.
- Listy źródeł nie podajesz: wdrożeniowiec dostanie to, co
  odczytałeś, i fragmenty kodu zacytowane jako przyczyna.
