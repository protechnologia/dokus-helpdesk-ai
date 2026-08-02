# Porównanie modeli parsujących

| | |
|---|---|
| Data pomiaru | Anthropic 2026-08-01 · OpenAI 2026-08-02 |
| Prompt | `parse_ticket.md` (`c36eec0`) |
| Słownik rozstrzygnięć | `naprawione`, `bez_zmian_w_systemie`, `brak` |
| Próbka | 10 zgłoszeń |

**Wynik: `gpt-4.1-mini` (82,6 pkt), `gpt-4.1` (70,7), `gpt-5.4` (70,5)** — pełne wyliczenie
w sekcji „Rekomendacja" na końcu. Wykluczone: `haiku`, `gpt-5.4-mini` i `o4-mini` — wszystkie trzy
wpisały niepotwierdzoną hipotezę do `cause`.

## Cena i czas

| miara | haiku 4.5 | sonnet 5 | gpt-4.1-mini | gpt-4.1 | gpt-5.4-mini | gpt-5.4 | o4-mini |
|---|---:|---:|---:|---:|---:|---:|---:|
| Stawka wejścia (za 1M) | $1,00 | $3,00 | $0,40 | $2,00 | $0,75 | $2,50 | $1,10 |
| Stawka wyjścia (za 1M) | $5,00 | $15,00 | $1,60 | $8,00 | $4,50 | $15,00 | $4,40 |
| Koszt próbki | $0,069 | $0,287 | $0,023 | $0,119 | $0,045 | $0,158 | $0,103 |
| Średnio na zgłoszenie | $0,0069 | $0,0287 | $0,0023 | $0,0119 | $0,0045 | $0,0158 | $0,0103 |
| Koszt 33319 *(25 komentarzy)* | $0,038 | $0,187 | $0,014 | $0,069 | $0,026 | $0,082 | $0,042 |
| Czas 33319 | 5,8 s | 42 s | 9,5 s | 16,4 s | 3,3 s | 2,3 s | 11,9 s |
| Tokeny wyjścia (próbka) | ~3 600 * | ~8 900 * | 1 841 | 2 037 | 2 028 | 2 003 | **10 971** |
| Ekstrapolacja na korpus | ~$10 | ~$43 | ~$3,5 | ~$18 | ~$7 | ~$24 | ~$15 |

\* Wartości gwiazdkowane są **wyliczone wstecz z kosztu**, nie odczytane z przebiegu — sumy tokenów
dla obu modeli Anthropic nie zostały zapisane. Rachunek zgadza się co do grosza, ale zależy od
przyjętego wejścia (~51 tys. tokenów, zmierzone u modeli OpenAI na tym samym prompcie); ±10% wejścia
przesuwa wyjście o ±10% przy Sonnecie i ±28% przy Haiku.

`o4-mini` produkuje **5× więcej tokenów wyjścia** przy porównywalnej długości artefaktu — to tokeny
rozumowania, których wołający nie widzi, a które są w pełni płatne. Stąd model tani w stawce wypada
drożej niż `gpt-4.1`.

**Sonnet 5 jest droższy od `gpt-5.4` zużyciem, nie cennikiem.** Stawka wyjścia jest u obu
identyczna ($15), wejścia wyższa o 20% — a rachunek o 82%, bo Sonnet wyprodukował ~4,4× więcej
tokenów wyjścia przy tym samym prompcie i artefaktach podobnej długości (śr. `solution` 293 vs
256 znaków). Nadmiar nie idzie w treść pliku. Ten sam mechanizm widać u niego w czasie: 42 s na
zgłoszeniu 33319 wobec 2,3 s u `gpt-5.4`.

Zgłoszenie 33319 pochłania 30–55% kosztu całej próbki u każdego modelu. Długie wątki zdominują
rachunek za korpus, a ich udział rośnie szybciej niż liczba zgłoszeń.

## Analiza parsowania

Średnie długości liczone **po rekordach niepustych** — pustki mają własny wiersz, więc wliczanie ich
do średniej mierzyłoby to samo dwa razy.

| miara | chat *(odniesienie)* | haiku | sonnet | gpt-4.1-mini | gpt-4.1 | gpt-5.4-mini | gpt-5.4 | o4-mini |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Zgodnych z `ParsedTicket` | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| Różnych wartości `component` | 2 | 6 | 1 | 1 | 1 | 1 | 5 | 1 |
| Rozpoznał ePUAP tam, gdzie chat *(24506, 34287)* | 2/2 | 2/2 | 0/2 | 0/2 | 0/2 | 0/2 | **2/2** | 0/2 |
| `resolution = naprawione` | 3 | 2 | 2 | 3 | 3 | 3 | 2 | 1 |
| `resolution = bez_zmian_w_systemie` | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| Puste `solution` | 5/10 | 7/10 | 7/10 | 6/10 | 6/10 | 6/10 | 6/10 | **9/10** |
| Puste `cause` | 9/10 | 9/10 | 10/10 | 10/10 | 10/10 | 9/10 | 10/10 | 9/10 |
| Puste `questions_summary` | 8/10 | 9/10 | 8/10 | 8/10 | 9/10 | **7/10** | 8/10 | 7/10 |
| Śr. długość `solution` (znaki) | 355 | 203 | 293 | 322 | **364** | 266 | 256 | 247 |
| Śr. długość `questions_summary` | 255 | 317 | 166 | 120 | 207 | 233 | 179 | 187 |
| Znalezione `error_codes` | 1 | 0 | 0 | 1 | 1 | 0 | 1 | 0 |

Rozproszenie `component` znaczy co innego u każdego z dwóch modeli, które je mają. U `haiku` to
bałagan (`eSOD` i `ESOD` obok siebie, `serwer DOKUS`, `usługa ePUAP`) — przy 1500 wywołaniach pole
byłoby bezużyteczne. U `gpt-5.4` to **rozdzielczość**: pięć wartości, w tym trafione `ePUAP`
dokładnie w tych zgłoszeniach, w których rozpoznał je chat. Pozostałych pięć modeli spłaszcza
wszystko do `główna aplikacja` i **traci to rozróżnienie**.

## Ocena merytoryczna

**Skala 1–5:** 5 = wzorcowo · 4 = dobrze, drobne braki · 3 = poprawnie, bez wartości dodanej ·
2 = wada wymagająca poprawy promptu lub przebiegu · 1 = wada dyskwalifikująca.
Każda pozycja sprawdzona wobec wątku źródłowego.

| kryterium | chat | haiku | sonnet | 4.1-mini | 4.1 | 5.4-mini | 5.4 | o4-mini |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Niezmyślanie przyczyny (`cause`) | 5 | **1** | 5 | 5 | 5 | **2** | 5 | **1** |
| Zapis odrzuconej hipotezy | 5 | 2 | 4 | 2 | 3 | 3 | 4 | **1** |
| Rozstrzygnięcie z długiego wątku (33319) | **2** | 4 | 4 | 5 | 5 | 4 | **2** | **2** |
| Zgłoszenie informacyjne (33644) | 5 | 2 | 2 | 2 | **5** | 2 | **5** | 2 |
| Rozdzielczość `component` | 5 | **1** | 3 | 3 | 3 | 3 | **5** | 3 |
| Kompletność `solution` | 5 | 3 | 4 | 4 | 5 | 4 | 4 | **2** |
| Konkrety w `questions_summary` | 5 | 3 | 3 | 3 | 3 | **5** | 3 | 3 |
| Zgodność z zasadą 9 | 5 | **1** | 5 | 5 | 5 | **2** | 5 | **1** |
| **Przydatność do przebiegu** | n/d | **1** | 4 | 3 | 4 | **2** | **5** | **1** |

Uzasadnienia ocen krytycznych:

| model | co się stało |
|---|---|
| `haiku` | w 11312 wpisał do `cause` „problem prawdopodobnie wynika z infrastruktury sieciowej" — hipotezę obaloną w tym samym wątku, jako ustaloną przyczynę |
| `gpt-5.4-mini` | ta sama wada w łagodniejszej formie: `cause` = „Prawdopodobnie problemy z infrastrukturą sieciową"; słowo „prawdopodobnie" nie ratuje pola, które ma nieść przyczynę ustaloną |
| `o4-mini` | najgorszy wariant tej wady: `cause` = „Problemy z infrastrukturą sieciową" **bez cienia zastrzeżenia**, przy `solution = brak` — zostaje sama zmyślona przyczyna, bez kontekstu, który by ją podważał. Do tego 9/10 pustych `solution` |
| `chat`, `gpt-5.4`, `o4-mini` przy 33319 | zgubiły rozstrzygnięcie w najdłuższym wątku (`resolution = brak`), mimo że wątek kończy się potwierdzeniem naprawy |
| `gpt-4.1`, `gpt-5.4` przy 33644 | **jedyne poza czatem** ocaliły treść zgłoszenia informacyjnego (wykaz zmian wersji); pozostałe wyrzuciły wszystko |
| `gpt-5.4-mini` przy 11312 | **jedyny** wyłowił pytania diagnostyczne z wątku; `sonnet`, `gpt-5.4` i `o4-mini` wpisały tam pytanie proceduralne, którego prompt zakazuje |

## Wnioski

| # | wniosek | konsekwencja |
|---|---|---|
| 1 | Zmyślanie przyczyny nie jest wadą jednego modelu ani jednej rodziny | powtórzyło je 3 z 7 modeli, w obu rodzinach i na obu poziomach cenowych — to **luka promptu**, nie własność dostawcy |
| 2 | `gpt-5.4` wygrywa na rozdzielczości `component` | jako jedyny model trafił `ePUAP` tam, gdzie chat; pozostałe spłaszczają do `główna aplikacja`, tracąc rozróżnienie bez zostawiania śladu |
| 3 | Model rozumujący nie pomógł | `o4-mini` ma najgorszy wynik merytoryczny w zestawie przy 5× większym zużyciu tokenów wyjścia — rozumowanie poszło w koszt, nie w jakość |
| 4 | Cena nie przewiduje jakości | `gpt-4.1-mini` (najtańszy, ~$3,5 za korpus) wypada lepiej niż `gpt-5.4-mini` i `o4-mini`, bo nie zmyśla przyczyny |
| 5 | **Luka promptu:** zgłoszenia informacyjne | 5 z 8 wariantów wyrzuciło całą treść 33644; CLAUDE.md liczy ~40 takich rekordów („dokumentacja, nie incydent") — do rozstrzygnięcia przed etapem 10 |
| 6 | **Luka promptu:** zakaz pytań proceduralnych działa słabo | 3 modele mimo zakazu wpisały „czy po zmianie jest lepiej" do `questions_summary` |
| 7 | Limity szybkości zatrzymają przebieg na korpusie | `gpt-4.1` dostał HTTP 429 przy dziesiątym zgłoszeniu; wznawianie po identyfikatorach jest wymogiem etapu 10, nie udogodnieniem |

## Rekomendacja

Punktacja składa trzy tabele w jedną liczbę. **Reguły przeliczania są jawne**, żeby wynik dało się
sprawdzić i zakwestionować — bez nich „punkty" byłyby oceną autora przebraną za arytmetykę.

| składowa | waga | źródło | jak liczona |
|---|---:|---|---|
| Jakość | 40% | średnia 8 ocen merytorycznych (bez wiersza zbiorczego) | skala 1–5 przeskalowana na 0–100 |
| Cena | 40% | koszt korpusu z tabeli cenowej | najtańszy = 100, najdroższy = 0, reszta liniowo |
| Czas | 20% | czas zgłoszenia 33319 | najszybszy = 100, najwolniejszy = 0, reszta liniowo |

**Próg wstępny:** model z oceną ≤2 za *niezmyślanie przyczyny* odpada bez punktacji. Bez tego progu
uśrednianie pozwala nadrobić taniością wadę, którą zasada 9 traktuje jako dyskwalifikującą —
a wtedy `gpt-5.4-mini` wchodzi na drugie miejsce mimo zmyślonej przyczyny.

**Odpadają: `haiku` (ocena 1), `gpt-5.4-mini` (2), `o4-mini` (1).**

| # | model | **punkty** | jakość | cena | czas | śr. ocen | koszt korpusu |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | `gpt-4.1-mini` | **82,6** | 65,6 | 100,0 | 81,9 | 3,62 | ~$3,5 |
| 2 | `gpt-4.1` | **70,7** | 81,2 | 63,3 | 64,5 | 4,25 | ~$18 |
| 3 | `gpt-5.4` | **70,5** | 78,1 | 48,1 | 100,0 | 4,12 | ~$24 |
| 4 | `sonnet 5` | **27,5** | 68,8 | 0,0 | 0,0 | 3,75 | ~$43 |

Trzy rzeczy, których sam ranking nie pokazuje:

- **Miejsca 2 i 3 dzieli 0,2 punktu** — to szum, nie różnica. Wybór między `gpt-4.1` a `gpt-5.4`
  rozstrzygają kryteria spoza punktacji: `gpt-5.4` jako jedyny trafia `component`, `gpt-4.1` ma
  wyższą średnią ocen i jest o $6 tańszy.
- **Zwycięzca wygrywa ceną, nie jakością** — `gpt-4.1-mini` ma trzecią jakość w stawce (3,62), ale
  jest 5× tańszy od `gpt-4.1`. Przy wadze ceny 40% to przesądza. Gdyby jakość ważyła 60%, pierwsze
  miejsce zająłby `gpt-4.1`.
- **Sonnet 5 przegrywa podwójnie** — najdroższy i najwolniejszy w zestawie, przy jakości niższej niż
  oba modele `gpt-4.1`. Zero punktów w dwóch składowych to nie kara za mało — to skutek skalowania
  do skrajności zestawu.

**Wybór zależy od tego, co jest ograniczeniem.** Budżet → `gpt-4.1-mini`. Jakość artefaktu, którego
nie da się przeparsować bez ponownego kosztu (zasada 7) → `gpt-4.1` albo `gpt-5.4`.
