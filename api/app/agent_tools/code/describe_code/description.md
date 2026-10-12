<!-- Opis narzędzia `describe_code` — czyta go MODEL razem ze
     schematem argumentów (`DescribeCodeQuery` bez docstringów),
     w każdym grafie, który ma to narzędzie na liście. Mówi, jak pytać
     narzędzie i co ono oddaje; po co wyniki w danej funkcji, mówi
     prompt grafu.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty w tabelce, wynik w JEDNEJ tabelce — pola zagnieżdżone
     pełną ścieżką (`sections[].section.title`), linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki argumentów.

     Ten plik to opis NARZĘDZIA. Opis PROJEKTU, który narzędzie
     oddaje, leży w paczce kodu (`project.md` obok `manifest.json`)
     i pisze go człowiek.

     Zasady wymieniają po nazwie szukanie (`find_code_text`), spis
     katalogu (`list_code_files`) i odczyt pliku (`read_code_file`),
     w kolejności użycia: z opisu bierze się katalog, a katalogu nie
     da się przeczytać. Pilnuje tego test opisu.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Mówi ci, jak zbudowana jest aplikacja, której kod czytasz: z jakich
części się składa, w którym katalogu leży kod której z nich i czego
w tym kodzie nie ma. Użyj, gdy nie wiesz, od którego katalogu zacząć
albo w której części kodu szukać dalej.

# Jak wywoływać

Bez argumentów.

# Co zwraca

JSON z opisem projektu i z tym, z której wersji kodu on pochodzi:

| pole                  | co zawiera                                |
|-----------------------|-------------------------------------------|
| package_info.branch   | gałąź kodu; `null`, gdy nieznana          |
| package_info.built_on | dzień, z którego pochodzi kopia kodu      |
| description           | opis projektu, tekst w Markdownie         |

# Zasady

- Opis jest jeden dla całego kodu i nie zmienia się w trakcie
  sprawy.
- Z opisu bierzesz katalog. W tym katalogu szukasz
  (`find_code_text`, w `path`) albo oglądasz pliki
  (`list_code_files`). O tym, jak aplikacja się zachowuje,
  mówi dopiero kod przeczytany narzędziem `read_code_file`.
- Kod, który czytasz, pochodzi z jednej gałęzi
  (`package_info.branch`). Instalacja klienta może stać na innej.
- Sam opis nie trafia na listę źródeł odpowiedzi.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
