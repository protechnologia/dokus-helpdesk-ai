# Porównanie modeli parsujących: Haiku 4.5 vs Sonnet 5

**Data pomiaru:** 2026-08-01 · **Prompt:** `api/app/prompts/parse_ticket.md` (wersja z commita `c36eec0`)
· **Słownik rozstrzygnięć:** wersja 1 · **Próbka:** 10 zgłoszeń, `data/parsed/{chat,haiku,sonnet}/`

Dokument rozstrzyga, którym modelem puścić masowe parsowanie korpusu (etap 10). Trzeci wariant —
`chat/`, parsowany ręcznie w rozmowie mocniejszym modelem — jest **punktem odniesienia jakości**,
nie kandydatem: tamtej drogi nie da się uruchomić na 1500 zgłoszeniach.

## Wynik

**Rekomendacja: Sonnet 5.** Haiku ma jedną wadę dyskwalifikującą (zapisuje niepotwierdzone
hipotezy w polu `cause`) i destabilizuje `component`. Cena rekomendacji: **4,2× wyższy koszt**.

## Koszt i czas

| | Haiku 4.5 | Sonnet 5 |
|---|---:|---:|
| Stawka wejścia / wyjścia (za 1M tokenów) | $1 / $5 | $3 / $15 |
| Koszt próbki (10 zgłoszeń) | **$0,069** | **$0,287** |
| Średnio na zgłoszenie | $0,0069 | $0,0287 |
| Najdroższe zgłoszenie (33319, 25 komentarzy) | $0,038 / 5,8 s | **$0,187 / 42 s** |
| **Ekstrapolacja na korpus (~1500 zgłoszeń)** | **~$10** | **~$43** |

Różnica kosztu (4,2×) jest wyższa niż różnica stawek (3×) — Sonnet produkuje więcej tokenów
wyjścia. Zgłoszenie 33319 kosztowało u Sonnet **2,7× więcej niż pozostałe dziewięć razem**;
długie wątki są nieproporcjonalnie drogie i to one zdominują rachunek za korpus.

## Jakość — metryki mierzalne

| | chat *(odniesienie)* | Haiku 4.5 | Sonnet 5 |
|---|---|---|---|
| Poprawnych artefaktów | 10/10 | 10/10 | 10/10 |
| Przechodzi kontrakt `ParsedTicket` | tak | tak | tak |
| Różnych wartości `component` | 2 | **6** | 1 |
| `resolution = naprawione` | 3 | 2 | 2 |
| Puste `solution` | 5/10 | 7/10 | 7/10 |
| Puste `questions_summary` | 8/10 | 9/10 | 8/10 |
| Śr. długość `solution` (znaki) | 179 | 63 | 90 |
| Śr. długość `questions_summary` | 54 | 36 | 36 |
| Znalezione `error_codes` | 1 | 0 | 0 |

## Jakość — ocena merytoryczna

Cztery zgłoszenia, w których warianty się rozeszły. Każde sprawdzone wobec wątku źródłowego.

### 33319 — najdłuższy wątek (25 komentarzy), rozstrzygnięcie na końcu

Wątek kończy się prośbą o potwierdzenie, że podglądy działają już poprawnie — czyli rozwiązanie
w nim jest.

| | ocena |
|---|---|
| chat | **błąd** — `resolution=brak`, zgubił rozstrzygnięcie |
| Haiku | trafnie — `naprawione` + zastrzeżenie o wcześniej wygenerowanych dokumentach |
| Sonnet | **najlepiej** — `naprawione`, a w `solution` zapisał, że dostawca potwierdził naprawę **bez podania szczegółu technicznego**; nie udaje wiedzy, której w wątku nie ma |

To jedyne zgłoszenie, w którym wariant z czatu przegrywa — i nieprzypadkowo: rozstrzygnięcie tonie
tu w 25 komentarzach ze stopkami i klauzulami RODO.

### 11312 — „naprawiono skutki, nie przyczynę" (18% korpusu wg CLAUDE.md)

Hipotezę o braku miejsca na dysku obalono w tym samym wątku; sprawę zamknięto wskazaniem na
infrastrukturę klienta, bez potwierdzenia.

| | ocena |
|---|---|
| chat | wzorcowo — `cause` zapisuje **odrzuconą hipotezę** jako odrzuconą, `solution` mówi wprost, że problem nie ustąpił |
| Haiku | **wada dyskwalifikująca** — w `cause` wpisał *„problem prawdopodobnie wynika z infrastruktury sieciowej"*, czyli **niepotwierdzoną hipotezę jako ustaloną przyczynę**. Prompt tego zakazuje wprost. Dodatkowo przeniósł ścieżkę instalacji, wbrew regule „nie przenoś wartości tej instalacji" |
| Sonnet | dobrze — `cause=brak`, ale całą historię łącznie z „to nie rozwiązało problemu" ocalił w `solution` |

### 33644 — zgłoszenie informacyjne (wykaz zmian wersji, komentarz „Zamykam")

| | ocena |
|---|---|
| chat | ocalił treść — 660 znaków z wykazem funkcji, zastrzeżeniem o pozycjach odłożonych na później i uwagą, że dotyczy **wyłącznie środowiska testowego** |
| Haiku i Sonnet | oba `solution=brak` — **wyrzuciły całą treść** |

Formalnie modele mają rację (to nie zgłoszenie problemu). Merytorycznie: rekord został pusty,
choć niósł wiedzę o wersji i funkcjach. **To luka promptu, nie modelu** — patrz „Wnioski".

### `questions_summary` — pole, w którym różnica jest największa

| zgłoszenie | chat | Haiku | Sonnet |
|---|---|---|---|
| 32011 | pełne, z konkretami | pełne, z konkretami | pełne, z konkretami |
| 11312 | pełne, z konkretami | **`brak`** — zgubił pytania, które w wątku były | pytanie **proceduralne**, którego prompt zakazuje |

Przy 32011 wszystkie trzy warianty zachowały nazwy własne i etykiety z interfejsu — pole działa
zgodnie z zamierzeniem. Przy 11312 zawiodły oba modele, każdy inaczej.

## `component` — Haiku destabilizuje pole

| wariant | wartości na 10 rekordach |
|---|---|
| chat | `główna aplikacja` ×8, `ePUAP` ×2 |
| Sonnet | `główna aplikacja` ×10 |
| **Haiku** | **6 różnych**: `główna aplikacja` ×5, `eSOD`, `ESOD`, `serwer DOKUS`, `usługa ePUAP`, `ePUAP i eDoreczenia` |

Haiku materializuje ryzyko zapisane w CLAUDE.md („warianty zapisu tej samej usługi są niemal
pewne"): przy 1500 wywołaniach pole byłoby bezużyteczne nawet jako opisowe, a normalizacja
wymagałaby osobnego przebiegu.

Sonnet ma odwrotną skazę, łagodniejszą: spłaszcza wszystko do `główna aplikacja` i **gubi `ePUAP`**
tam, gdzie chat go rozpoznał (24506, 34287). Traci się rozróżnienie, ale nie powstaje bałagan.

## Wnioski

1. **Haiku odpada przez `cause`.** Zapis hipotezy jako ustalonej przyczyny przy 1500 rekordach
   daje indeks pełen zmyślonych przyczyn wyglądających na wiedzę — gorzej niż brak trafienia,
   bo wygląda na odpowiedź (CLAUDE.md → zasada 9).
2. **Sonnet nie konfabuluje.** Gdy nie umie rozstrzygnąć, przenosi treść do `solution` i zaznacza
   niepewność, zamiast zgadywać. To jedyne zachowanie zgodne z zasadą 9 na trudnych wątkach.
3. **Różnica chat ↔ modele nie dowodzi wyższości modelu z czatu.** Tam pracował inny, mocniejszy
   model, w rozmowie z człowiekiem. Dziesięć plików to za mało na wniosek o rodzinach modeli —
   to raczej dowód, że **przy tym prompcie próg jakości leży wysoko**.
4. **Dwie luki promptu, niezależne od modelu** (do rozstrzygnięcia przed etapem 10):
   - **zgłoszenia informacyjne** (wykaz zmian, opis funkcji) nie mają obsługi — dwa z trzech
     wariantów wyrzuciły całą treść, a CLAUDE.md liczy ~40 takich rekordów („dokumentacja, nie
     incydent");
   - **zakaz pytań proceduralnych działa słabo** — Sonnet mimo zakazu wpisał pytanie typu „czy
     po zmianie jest lepiej".
5. **Czas przebiegu.** 42 s na jedno zgłoszenie u Sonnet przy 25 komentarzach; przy 1500 rekordach
   przebieg to kilka godzin. Komenda zapisuje artefakt po każdym zgłoszeniu, więc przerwanie nie
   niszczy opłaconej pracy — ale wznawianie po identyfikatorach trzeba mieć przemyślane (etap 10).

## Ograniczenia tego pomiaru

- **Próbka to 10 zgłoszeń dobranych pod skrajności**, nie materiał statystyczny. Wnioski o `cause`
  i `component` są mocne (widoczne w wielu rekordach naraz); ocena pojedynczych zgłoszeń opiera
  się na 2–3 przypadkach.
- **Jedno przejście na model.** CLAUDE.md wymaga powtórzenia ewaluacji ≥2 razy, bo `temperature=0`
  nie daje determinizmu. Tu tego nie zrobiono — a przy Sonnet 5 jest to **niewykonalne parametrem**:
  model odrzuca `temperature` z błędem HTTP 400 (patrz `MODELS_ACCEPTING_TEMPERATURE`
  w `api/app/llm/client_claude.py`).
- **Oceniał autor promptu**, nie niezależny sędzia — CLAUDE.md ostrzega przed tym wprost
  („Nie rób autora tekstów sędzią").
- **Nie mierzono `recall@5`** ani żadnej metryki retrievalu; to osobna oś, etap 3.
