# Pomiar embedderów — `recall@K` i MRR na golden secie

| | |
|---|---|
| Data | 2026-08-05 |
| Skrypt | `scripts/eval_embeddings.py` |
| Golden set | `data/golden/bielik-11b-golden200.json` — 165 zapytań syntetycznych |
| Korpus | `data/parsed/bielik-11b-golden200/` — 200 rekordów, **nieprzefiltrowany** (odrzucone zostają jako dystraktory) |
| Sprzęt | CPU, ~90 s na model i tryb (200 rekordów + 165 zapytań) |

**Wnioski w jednym zdaniu:** tryb **`query→passage` wygrywa** z `sts→sts` (cztery pomiary, wszystkie
w tę samą stronę), ale **wyboru modelu ten pomiar NIE rozstrzyga** — `recall@1` na poziomie 98%
oznacza sufit, przy którym kandydaci zmieszczą się w granicach jednego zapytania.

## Wyniki

Zapytania **surowe** (tak, jak wpływają do helpdesku). Oś „zapytanie sparsowane" nie została
zmierzona — wymaga przebiegu LLM po zapytaniach, patrz „Czego nie zmierzono".

### Po zaostrzeniu zapytań (pomiar wiążący)

| model | tryb | @1 | @2 | @3 | @4 | @5 | MRR |
|---|---|---:|---:|---:|---:|---:|---:|
| **PolDense-150M** | `query→passage` | **98,2** | 98,8 | 99,4 | 100,0 | 100,0 | **0,988** |
| **PolDense-150M** | `sts→sts` | 97,0 | 98,2 | 98,8 | 99,4 | 99,4 | 0,980 |
| Nomic v1.5 *(kontrola)* | `query→passage` | 87,9 | 90,3 | 93,3 | 95,2 | 95,2 | 0,910 |
| Nomic v1.5 *(kontrola)* | `sts→sts` | 84,2 | 88,5 | 89,7 | 91,5 | 92,1 | 0,878 |

Rozbicie PolDense · `query→passage`: eksploatacyjne **99,3** (n=137) · wdrożeniowo-migracyjne
**92,9** (n=28) · typowe **96,8** (n=94) · trudne **100,0** (n=71).

### Przed zaostrzeniem (dla porównania)

| model | tryb | @1 | MRR |
|---|---|---:|---:|
| PolDense-150M | `query→passage` | 98,8 | 0,992 |
| PolDense-150M | `sts→sts` | 98,2 | 0,988 |
| Nomic v1.5 | `query→passage` | 90,9 | 0,932 |
| Nomic v1.5 | `sts→sts` | 86,1 | 0,895 |

## Co rozstrzygnięte: tryb

**`query→passage` > `sts→sts`** — konsekwentnie, w czterech niezależnych pomiarach:

| model | query→passage | sts→sts | różnica |
|---|---:|---:|---:|
| PolDense (po zaostrzeniu) | 98,2 | 97,0 | −1,2 pp |
| PolDense (przed) | 98,8 | 98,2 | −0,6 pp |
| Nomic (po zaostrzeniu) | 87,9 | 84,2 | −3,7 pp |
| Nomic (przed) | 90,9 | 86,1 | −4,8 pp |

**Zastrzeżenie, które ogranicza ten wniosek:** argument za `sts→sts` z CLAUDE.md zakładał
**zapytanie sparsowane** („po sparsowaniu obie strony to ten sam gatunek tekstu"). Tego wariantu
nie zmierzono. Przy zapytaniu surowym `sts→sts` porównuje mail z podsumowaniem — czyli dwie różne
rzeczy — i to może tłumaczyć całą różnicę. **Decyzja o skasowaniu named vectora `sts` wymaga
domknięcia osi parsera.**

## Czego pomiar NIE rozstrzyga: wybór modelu

`recall@1` = 98,2% to sufit. Pozostali kandydaci (PolDense-68M, mmlw-roberta-large, BGE-M3,
Nomic v2-moe) najpewniej wylądują w przedziale 96–100%, czyli w granicach **jednego–dwóch
zapytań** na 165. Wybór na tej podstawie byłby wyborem na podstawie szumu.

### Grupa kontrolna — dlaczego wiemy, że to sufit, a nie jakość modelu

Do pomiaru dołożono **`nomic-embed-text-v1.5`** — model trenowany prawie wyłącznie na angielskim,
który na polskim korpusie **powinien** wypaść wyraźnie słabiej. Progi interpretacji ustalono
**przed** przebiegiem: ≥95% oznaczałoby „zadanie za łatwe", 60–75% — „pomiar różnicuje".

Wyszło **87,9%** — pomiędzy, bliżej pierwszego. Anglojęzyczny model trafia 9 na 10 zapytań
w pierwszy strzał na polskim korpusie, więc sygnał w zapytaniach jest w dużej mierze leksykalny.

Kontrola dała jednak dwie rzeczy, których sam pomiar PolDense nie dawał:
- **rozstęp 10,3 pp** między modelem dobrym a kontrolnym — czyli pomiar różnicuje, tylko nie
  w zakresie, w którym leżą kandydaci;
- **potwierdzenie, że etykiety trudności coś znaczą.** U Nomica warstwa „trudne" wypada gorzej
  (85,9%) niż „typowe" (89,4%), czyli tak, jak powinna. U PolDense obie mają 100% — model jest
  na tyle dobry, że ich nie odczuwa.

### Zaostrzenie zapytań — co dało

Usunięto **18 zapytań** sygnatury spraw, numery ewidencyjne, nazwy plików i wersje. Komunikaty
błędów **zostawiono** — użytkownik realnie je wkleja, więc to uczciwy sygnał.

| model | @1 przed | @1 po | strata |
|---|---:|---:|---:|
| PolDense | 98,8 | 98,2 | **−0,6** |
| Nomic (kontrola) | 90,9 | 87,9 | **−3,0** |

**Nomic stracił pięciokrotnie więcej.** To potwierdza, że usunięte ciągi były sygnałem
leksykalnym: model bez znajomości polskiego rozpoznawał je jako identyfikatory, model rozumiejący
język ich nie potrzebował.

Zysk dla pomiaru realny (rozstęp urósł z 7,9 do 10,3 pp), ale **za mały, by zmienić jego charakter** —
18 zapytań to 11% zestawu, a warstwa „trudne" u PolDense pozostała nietknięta (100%, MRR 1,000).

## Dlaczego zadanie jest za łatwe

Trzy przyczyny, w kolejności wagi:

1. **Korpus ma 200 rekordów**, docelowy indeks ~1400. Trafienie w top-5 z 200 to trafienie
   w 2,5% zbioru; z 1400 byłoby to 0,36% — siedmiokrotnie trudniej. Brakuje też dystraktorów
   **z tej samej klasy problemu**, a to jest realna trudność produkcyjna (sześć zgłoszeń „nic nie
   przychodzi z e-Doręczeń" o sześciu różnych przyczynach).
2. **Zapytania pisane z rekordem przed oczami.** Nawet unikając cytowania, autor odtwarza
   strukturę i słownictwo pól `problem`/`symptoms` — czyli dokładnie tych, które są embedowane.
   Parafrazowanie tego nie naprawi: parafraza to wciąż ta sama treść, a embedder semantyczny
   istnieje właśnie po to, by parafrazy rozpoznawać.
3. **Zapytania są dobrze ustrukturyzowane** (mediana 138 zn.), podczas gdy realne zgłoszenia bywają
   jednozdaniowe.

## Czego nie zmierzono

- **Oś „zapytanie surowe vs sparsowane"** — wymaga przepuszczenia 165 zapytań przez
  `helpdesk tickets parse`, czyli działającego LLM-a (pod z Bielikiem, ~15 min, <$0,50).
  Bez niej decyzja o trybie jest połowiczna, bo argument za `sts→sts` dotyczy właśnie zapytań
  sparsowanych.
- **Pozostali kandydaci** (PolDense-68M, mmlw, BGE-M3, Nomic v2-moe) — nie ma sensu ich mierzyć,
  dopóki metryka ma sufit.
- **Prefiksy mmlw** wpisane w `MODEL_PREFIXES` **z pamięci** i wymagają potwierdzenia na karcie
  modelu przed pomiarem. To dokładnie ten rodzaj wartości, który przekrzywia porównanie, gdy się
  go zgadnie.

## Rekomendacja

**Przed wyborem modelu rozszerzyć korpus do pełnych ~1400 rekordów.** To jedyna zmiana, która
realnie zmienia rząd trudności, i nie zależy od dyscypliny autora zapytań. Koszt: postawienie poda
i ~2,5 h parsowania Bielikiem (~$2).

Alternatywa do rozważenia: **uznać, że przy tym korpusie wybór modelu nie ma znaczenia** i wziąć
najtańszy/najszybszy wariant. Jeśli cztery kandydatury mieszczą się w granicach szumu, to też jest
wynik — tylko trzeba go tak nazwać, zamiast udawać, że pomiar wskazał zwycięzcę.
