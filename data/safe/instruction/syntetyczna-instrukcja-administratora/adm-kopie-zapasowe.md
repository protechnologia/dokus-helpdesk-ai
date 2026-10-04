Kopię zapasową bazy i katalogu załączników wykonuje skrypt `kopia.sh`, uruchamiany z harmonogramu systemowego. Dokus sam kopii nie wykonuje i nie ostrzega, gdy jej nie ma.

Wpis w harmonogramie ma pięć pól czasu i polecenie. Najczęstszy błąd to zamiana pól godziny i minuty — skrypt uruchamia się wtedy o innej porze albo wcale.

Po każdym przebiegu skrypt dopisuje wiersz do pliku `kopia.log`:

- `BKP-000` — kopia wykonana, z rozmiarem pliku,
- `BKP-017` — brak miejsca w katalogu docelowym,
- `BKP-031` — baza odrzuciła połączenie.

Brak wiersza z bieżącą datą oznacza, że skrypt się nie uruchomił. Sam plik kopii w katalogu docelowym niczego nie dowodzi: przy błędzie `BKP-017` powstaje plik niepełny, o rozmiarze mniejszym niż poprzednie.

Kopie starsze niż 14 dni skrypt usuwa. Okres zmienia parametr `RETENCJA_DNI` na początku skryptu.
