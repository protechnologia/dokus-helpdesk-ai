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
- Przyjętego ADR nie edytuje się poza statusem. Zmiana decyzji to nowy ADR z polem „Zastępuje”,
  a w starym zmienia się tylko status na „Zastąpiona przez …”.
- Najcenniejsze są odrzucone opcje: powód odrzucenia stoi przy samej opcji, a „Koszty” mówią
  tylko o cenie opcji wybranej.
- Bez danych klienta: wnioski i liczby, bez cytatów z korpusu i bez nazw osób (folder jest
  w repo).
- Nową dużą decyzję zapisujemy od razu; istniejące przenosimy przy refaktoryzacji podsekcji
  CLAUDE.md. Decyzja zapisana wstecz ma w statusie datę przyjęcia; datę zapisu pokazuje git.
- Nazwa pliku: `<PREFIKS>-<NNN>_<krótka-nazwa>.md`, numer kolejny w obszarze.
- Gdy decyzja nie pasuje do żadnego obszaru, agent proponuje nowy (prefiks, nazwa, sekcje
  CLAUDE.md) i dopisuje go do tabeli dopiero po akceptacji użytkownika.

## Obszary

| prefiks | obszar                                                        | sekcje CLAUDE.md                                    |
|---------|---------------------------------------------------------------|-----------------------------------------------------|
| PRD     | produkt i jego zasady                                         | Produkt                                             |
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

| ID                                                                   | decyzja                                                 | status              | zastępuje |
|----------------------------------------------------------------------|---------------------------------------------------------|---------------------|-----------|
| [AGT-001](AGT-001_zapytanie-w-ksztalcie-indeksu.md)                  | Zapytanie wektorowe pisze agent, w kształcie indeksu    | Przyjęta 2026-10-02 | —         |
| [AGT-002](AGT-002_opis-narzedzia-wspolny-dla-grafow.md)              | Opis narzędzia dla modelu jest jeden, przy narzędziu    | Przyjęta 2026-10-03 | —         |
| [AGT-003](AGT-003_narzedzia-wiedzy-dwustopniowo.md)                  | Wyszukiwanie oddaje identyfikatory, źródłem jest odczyt | Przyjęta 2026-10-04 | —         |
| [AGT-004](AGT-004_zrodlo-z-kodu-to-cytowana-przyczyna.md)            | Źródłem z kodu jest fragment zacytowany jako przyczyna  | Przyjęta 2026-10-06 | —         |
| [AGT-005](AGT-005_funkcja-sama-dociaga-material.md)                  | Każda funkcja sama dociąga materiał w swojej pętli      | Przyjęta 2026-10-02 | —         |
| [AGT-006](AGT-006_odpowiedz-grafu-narzedziem.md)                     | Odpowiedź grafu przychodzi narzędziem `respond_<graf>`  | Przyjęta 2026-10-02 | —         |
| [AGT-007](AGT-007_wariant-generacji-to-kod.md)                       | Wariant generacji to kod: osobny graf na wariant        | Przyjęta 2026-10-02 | —         |
| [AGT-008](AGT-008_zgodnosc-przyczyn-ocenia-agent.md)                 | Zgodność przyczyn ocenia agent w uwagach, nie kod       | Przyjęta 2026-10-11 | —         |
| [GAT-001](GAT-001_powiadomienie-nie-przechodzi-bramki-zamkniecia.md) | Powiadomienie nie przechodzi bramki zamknięcia          | Przyjęta 2026-11-20 | —         |

## Szablon

```markdown
# XXX-NNN: Tytuł decyzji

| pole      | wartość |
|-----------|---------|
| Status    | Proponowana / Przyjęta RRRR-MM-DD / Zastąpiona przez XXX-NNN / Odrzucona |
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
```
