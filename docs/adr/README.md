# Decyzje architektoniczne (ADR)

Jeden plik na decyzję: kontekst, rozważane opcje, wybór i konsekwencje. ADR odpowiada na
pytanie „dlaczego tak, a nie inaczej?”, na które nie odpowie ani kod, ani README. CLAUDE.md przy
decyzji trzyma regułę, to, co z niej wynika, i link do ADR.

Ten plik czyta się na początku każdej sesji (zasada w CLAUDE.md). Przed zmianą w obszarze
przeczytaj jego ADR-y ze statusem „Przyjęta”.

## Zasady

- Jedna decyzja na plik, najwyżej strona.
- ADR piszemy, gdy decyzja jest trudna do odwrócenia, był realny wybór albo ktoś zapyta „czemu
  tak?”. Drobne decyzje zostają jednym zdaniem w CLAUDE.md.
- Przyjętego ADR nie zmienia się merytorycznie. Zmiana decyzji to nowy ADR z polem „Zastępuje”,
  a w starym zmienia się tylko status na „Zastąpiona przez …”.
- Poprawka niemerytoryczna przyjętego ADR (literówka, martwy link, ścieżka albo nazwa po
  przeniesieniu w kodzie) jest dozwolona i dostaje wpis w sekcji „Log” na końcu pliku; sekcja
  dochodzi przy pierwszej takiej poprawce.
- Najcenniejsze są odrzucone opcje: powód odrzucenia stoi przy samej opcji, a „Koszty” mówią
  tylko o cenie opcji wybranej.
- Bez danych klienta: wnioski i liczby, bez cytatów z korpusu i bez nazw osób (folder jest
  w repo).
- Nową dużą decyzję zapisujemy od razu; istniejące przenosimy przy refaktoryzacji podsekcji
  CLAUDE.md. Decyzja zapisana wstecz ma w statusie datę przyjęcia; datę zapisu pokazuje git.
- Nazwa pliku: `ADR-<NNN>_<krótka-nazwa>.md`, numer kolejny w całym katalogu, bez przedrostka
  obszaru: obszar stoi w kolumnie spisu, a decyzja z dwóch obszarów nie musi wybierać jednego.
  Numer zastąpionej albo odrzuconej decyzji nie wraca.
- Gdy decyzja nie pasuje do żadnego obszaru, agent proponuje nowy (skrót, nazwa, sekcje
  CLAUDE.md) i dopisuje go do tabeli dopiero po akceptacji użytkownika.

## Obszary

Skrót obszaru stoi w kolumnie „obszar” spisu decyzji; w ID go nie ma.

| skrót   | obszar                                                        | sekcje CLAUDE.md                                    |
|---------|---------------------------------------------------------------|-----------------------------------------------------|
| PRD     | produkt i jego zasady                                         | Produkt, Zasady produktu                            |
| DAT     | dane: korpus zgłoszeń, instrukcje, kod aplikacji jako materiał | Dane                                                |
| DOM     | kontrakt karty zgłoszenia i filtr jakości                     | Domena                                              |
| GAT     | bramki jakości i „Popraw”                                     | Bramki jakości i asysta pisania                     |
| ANO     | anonimizacja                                                  | Usługa `anonymizer`                                 |
| IDX     | embedder i indeksy: Qdrant, Postgres                          | Warstwa embeddera, Qdranta, wyszukiwania tekstowego |
| AGT     | agent: narzędzia, węzły, grafy                                | Warstwa narzędzi agenta, węzłów, grafów             |
| LLM     | klienci modeli i prompty                                      | Warstwa LLM                                         |
| API     | trasy HTTP i komendy CLI                                      | Warstwa API, Warstwa CLI                            |
| FRO     | front pokazowy                                                | Frontend                                            |
| STR     | podział kodu, warstwy i styl                                  | Styl kodu i komentarzy                              |
| OPS     | uruchamianie, konfiguracja, deploy i testy                    | Uruchamianie i utrzymanie                           |

## Decyzje

| ID                                                                   | obszar | decyzja                                                 | status              | zastępuje |
|----------------------------------------------------------------------|--------|---------------------------------------------------------|---------------------|-----------|
| [ADR-001](ADR-001_zapytanie-w-ksztalcie-indeksu.md)                  | AGT    | Zapytanie wektorowe pisze agent, w kształcie indeksu    | Przyjęta 2026-10-02 | —         |
| [ADR-002](ADR-002_opis-narzedzia-wspolny-dla-grafow.md)              | AGT    | Opis narzędzia dla modelu jest jeden, przy narzędziu    | Przyjęta 2026-10-03 | —         |
| [ADR-003](ADR-003_narzedzia-wiedzy-dwustopniowo.md)                  | AGT    | Wyszukiwanie oddaje identyfikatory, źródłem jest odczyt | Przyjęta 2026-10-04 | —         |
| [ADR-004](ADR-004_zrodlo-z-kodu-to-cytowana-przyczyna.md)            | AGT    | Źródłem z kodu jest fragment zacytowany jako przyczyna  | Przyjęta 2026-10-06 | —         |
| [ADR-005](ADR-005_powiadomienie-nie-przechodzi-bramki-zamkniecia.md) | GAT    | Powiadomienie nie przechodzi bramki zamknięcia          | Przyjęta 2026-11-20 | —         |
| [ADR-006](ADR-006_funkcja-sama-dociaga-material.md)                  | AGT    | Każda funkcja sama dociąga materiał w swojej pętli      | Przyjęta 2026-10-02 | —         |
| [ADR-007](ADR-007_odpowiedz-grafu-narzedziem.md)                     | AGT    | Odpowiedź grafu przychodzi narzędziem `respond_<graf>`  | Przyjęta 2026-10-02 | —         |
| [ADR-008](ADR-008_wariant-generacji-to-kod.md)                       | AGT    | Wariant generacji to kod: osobny graf na wariant        | Przyjęta 2026-10-02 | —         |
| [ADR-009](ADR-009_zgodnosc-przyczyn-ocenia-agent.md)                 | AGT    | Zgodność przyczyn ocenia agent w uwagach, nie kod       | Przyjęta 2026-10-11 | —         |

## Szablon

```markdown
# ADR-NNN: Tytuł decyzji

| pole      | wartość |
|-----------|---------|
| Status    | Proponowana / Przyjęta RRRR-MM-DD / Zastąpiona przez ADR-NNN / Odrzucona |
| Zastępuje | — |
| Zadanie   | p. N planu albo commit |

## Kontekst

Problem i ograniczenia.

## Rozważane opcje

1. Opcja — odrzucona: dlaczego.
2. Opcja — wybrana.

## Decyzja

Wybrana opcja i dlaczego.

## Konsekwencje

### Zyski

- ...

### Koszty

- ...

## Log

Poprawki niemerytoryczne po przyjęciu, najnowsza na górze.

- RRRR-MM-DD — co poprawiono.
```

## Log

Zmiany zasad, obszarów, szablonu i układu tego pliku, najnowsza na górze. Nowy wiersz spisu
decyzji wpisu nie dostaje, bo widać go w spisie.

- 2026-11-25 — ID bez przedrostka obszaru: `ADR-NNN`, numer kolejny w całym katalogu, jak
  `RB-NNN` przy runbookach; obszar przeszedł do kolumny spisu, a „prefiks” w tabeli obszarów
  nazywa się „skrót”. Numery nadane według kolejności powstania plików: AGT-001 … AGT-004 →
  ADR-001 … ADR-004, GAT-001 → ADR-005, AGT-005 … AGT-008 → ADR-006 … ADR-009. Starsze opisy
  commitów mają dawne ID.
- 2026-11-25 — w zasadach i szablonie sekcja „Log” na poprawki niemerytoryczne ADR: przyjętego
  ADR nie zmienia się merytorycznie, a literówkę, martwy link albo ścieżkę po przeniesieniu
  wolno poprawić z wpisem w „Logu”; ten „Log” w README.
- 2026-11-25 — obszar PRD wskazuje sekcje „Produkt” i „Zasady produktu”, bo zasady produktu
  przeszły w CLAUDE.md do sekcji „Zasady”.
- 2026-11-20 — README z zasadami, obszarami z prefiksami, spisem decyzji i szablonem.
