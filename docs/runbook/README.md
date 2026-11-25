# Runbooki

Jeden plik na procedurę pracy nad projektem, której nie zapisuje kod: kroki, dostępy, koszt
i sprzątanie. Runbook odpowiada na pytanie „jak to zrobić?”, gdy czynność wychodzi poza repo
(konto u dostawcy, nasza maszyna), ma krok płatny, nieodwracalny albo decyzję człowieka i robi
się ją na tyle rzadko, że kolejność się zapomina. CLAUDE.md przy procedurze trzyma regułę i link
do runbooka.

Przed procedurą przeczytaj jej runbook, a po przejściu popraw go i dopisz wpis do „Logu”.

## Zasady

- Jedna procedura na plik. Nazwa pliku: `RB-<NNN>_<czynność>.md`, numer kolejny, czynność
  małymi literami i z łącznikami. Jeden przedrostek dla wszystkich runbooków, bez obszarów jak
  w ADR, żeby ID nie myliło się z decyzją; numer usuniętego runbooka nie wraca.
- CLAUDE.md, ADR i inne runbooki linkują do runbooka z ID jako tekstem linku
  (`[RB-001](…)`), tak jak do ADR.
- Runbook jest żywy, inaczej niż ADR: poprawia się go po każdym przejściu, a „Log” dostaje
  wpis z datą, tym, co przechodzono, wynikiem i tym, co w runbooku poprawiono. Żaden test
  runbooka nie uruchamia, więc procedura, której log długo milczy, może się nie zgadzać z kodem.
- Granica z README: procedura, której potrzebuje operator instancji (instalacja, konfiguracja,
  budowa materiałów, odświeżanie korpusu), stoi w całości w README, bez odsyłania tutaj. Runbook
  zostaje na nasze konta i maszyny, pomiary i utrzymanie dokumentacji. Żadna procedura nie stoi
  w obu miejscach.
- Granica z „Commands” w CLAUDE.md: pojedyncze polecenie zostaje tam, runbook to ciąg kroków.
- Granica z kodem: tego, co mówi `--help` albo docstring skryptu, runbook nie powtarza, tylko to
  wywołuje. Kod wklejony w runbook znaczy, że brakuje skryptu albo komendy.
- Bez sekretów, adresów infrastruktury i danych klienta, bo folder jest w repo: wartość stoi
  w ENV albo w pliku poza repo, a runbook mówi, skąd ją wziąć.
- Krok płatny albo nieodwracalny ma to napisane przy sobie, a agent pyta przed nim.
- Nową procedurę agent od razu proponuje jako runbook, zamiast zapisywać ją w swojej pamięci:
  pamięć jest prywatna dla jednej maszyny, a jej treść nie przechodzi przeglądu w commicie.
- Runbook, który ma powstać, stoi w „ToDo” z opisem (co i skąd wziąć treść) i tym, na co
  czeka; wpis znika, gdy runbook trafia do spisu.

## Spis

| ID                                                  | procedura                                      | kiedy                                           |
|-----------------------------------------------------|------------------------------------------------|-------------------------------------------------|
| [RB-001](RB-001_odchudzanie-podsekcji-claude-md.md) | Odchudzanie podsekcji CLAUDE.md                | co jakiś czas, jedna podsekcja CLAUDE.md naraz  |
| [RB-002](RB-002_pod-runpod-z-bielikiem.md)          | Pod na RunPodzie z Bielikiem dla anonimizatora | przed pracą z prawdziwym modelem anonimizującym |

## ToDo

| Lp. | Opis                                                                                                                                                                                                                                                               | Na co czeka                                              |
|-----|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|
| 1   | Wdrożenie na serwer pokazowy. Treść z notatki agenta z 2026-10-28, już nieaktualnej: wskazuje katalog kart golden200 skasowany 2026-11-11, a dziś na serwer idzie korpus 1115 kart i wątków. Adres serwera, klucz SSH i warstwa compose serwera zostają poza repo. | najbliższe wdrożenie, żeby kroki od razu były sprawdzone |
| 2   | Nowe karty golden setu: parsowanie do katalogu roboczego, indeks obok instancji, porównanie pomiarów i zastąpienie kart. Treść z CLAUDE.md, „Golden set retrievalu” i „Commands”.                                                                                  | krok 2 odchudzania podsekcji „Golden set retrievalu”     |

## Szablon

Sekcja bez treści wypada: procedura bez kosztu nie ma „Kosztu”, a bez sprzątania —
„Sprzątania”.

```markdown
# RB-NNN: Tytuł czynności

## Cel

Co ma być na końcu i po co.

## Kiedy

W jakiej sytuacji procedura rusza.

## Wymaga

- Dostęp, usługa albo program i skąd go wziąć.

## Koszt

- Za co się płaci, ile i kiedy licznik biegnie.

## Kroki

1. Krok — polecenie i oczekiwany wynik.

## Weryfikacja

Jak poznać, że się udało.

## Sprzątanie

Co zamknąć, usunąć albo przywrócić po pracy.

## Pułapki

- ...

## Powiązania

- Linki względne: [reguła w CLAUDE.md](../../CLAUDE.md#sekcja), ADR, inne runbooki, skrypty
  i testy, na których stoją kroki.

## Log

Najnowszy wpis na górze.

- RRRR-MM-DD — co przechodzono; wynik; co w runbooku poprawiono.
```

## Log

Zmiany zasad, szablonu i układu tego pliku, najnowsza na górze. Nowy wiersz spisu albo „ToDo”
wpisu nie dostaje, bo widać go w tabeli.

- 2026-11-25 — runbooki mają ID `RB-NNN` w nazwie pliku i tytule, a linki do nich mają ID
  jako tekst; dotąd nazwa bez numeru. Spis dostał kolumnę ID.
- 2026-11-25 — „ToDo” na runbooki do spisania (tabela: opis i na co czeka) i ten „Log”.
- 2026-11-25 — „Powiązania” w szablonie to linki względne.
- 2026-11-25 — README z zasadami, spisem i szablonem: Cel, Kiedy, Wymaga, Koszt, Kroki,
  Weryfikacja, Sprzątanie, Pułapki, Powiązania, Log.
