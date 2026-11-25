# Runbooki

Jeden plik na procedurę pracy nad projektem, której nie zapisuje kod: kroki, dostępy, koszt
i sprzątanie. Runbook odpowiada na pytanie „jak to zrobić?”, gdy czynność wychodzi poza repo
(konto u dostawcy, nasza maszyna), ma krok płatny, nieodwracalny albo decyzję człowieka i robi
się ją na tyle rzadko, że kolejność się zapomina. CLAUDE.md przy procedurze trzyma regułę i link
do runbooka.

Przed procedurą przeczytaj jej runbook, a po przejściu popraw go i dopisz wpis do „Logu”.

## Zasady

- Jedna procedura na plik, nazwa od czynności, bez numeru: `<czynność>.md`, małymi literami
  i z łącznikami. Do runbooka nikt nie odwołuje się numerem, a jego treść się zmienia.
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
- Runbook, który ma powstać, stoi w „ToDo” z tym, kiedy go spisać i skąd wziąć treść; wpis
  znika, gdy runbook trafia do spisu.

## Spis

| runbook                                                               | kiedy                                           |
|-----------------------------------------------------------------------|-------------------------------------------------|
| [Odchudzanie podsekcji CLAUDE.md](odchudzanie-podsekcji-claude-md.md) | co jakiś czas, jedna podsekcja CLAUDE.md naraz  |
| [Pod na RunPodzie z Bielikiem](pod-runpod-z-bielikiem.md)             | przed pracą z prawdziwym modelem anonimizującym |

## ToDo

- **Wdrożenie na serwer pokazowy** — spisać przy najbliższym wdrożeniu, żeby kroki od razu były
  sprawdzone. Treść: notatka agenta z 2026-10-28, już nieaktualna, bo paczka danych wskazuje
  katalog kart golden200, którego nie ma od 2026-11-11, a dziś na serwer idzie korpus 1115 kart
  i wątków. Adres serwera, ścieżka do klucza SSH i warstwa compose serwera zostają poza repo.
- **Nowe karty golden setu**: parsowanie do katalogu roboczego, indeks obok instancji,
  porównanie pomiarów i zastąpienie kart — spisać w kroku 2 odchudzania „Golden set
  retrievalu”. Treść: CLAUDE.md, „Golden set retrievalu” i „Commands”.

## Szablon

Sekcja bez treści wypada: procedura bez kosztu nie ma „Kosztu”, a bez sprzątania —
„Sprzątania”.

```markdown
# Tytuł: czynność

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
