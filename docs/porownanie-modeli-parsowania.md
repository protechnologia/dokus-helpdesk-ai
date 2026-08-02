# Porównanie modeli parsujących

| | |
|---|---|
| Data pomiaru | Anthropic 2026-08-01 · OpenAI i Bielik 2026-08-02 |
| Prompt | `parse_ticket.md` (`c36eec0`) |
| Słownik rozstrzygnięć | `naprawione`, `bez_zmian_w_systemie`, `brak` |
| Próbka | 10 zgłoszeń |

**Czołówka: `gpt-4.1-mini` (85,1 pkt), `gpt-4.1` (73,2), `gpt-5.4` (69,1)** — pełne wyliczenie
w sekcji „Rekomendacja". Cztery modele mają obniżony wynik za wpisanie niepotwierdzonej hipotezy
do `cause`: `gpt-5.4-mini`, `bielik-11b`, `haiku` i `o4-mini`.

**`bielik-11b` ocenia się osobno, gdy dane nie mogą opuścić infrastruktury klienta** — wtedy modele
chmurowe nie wchodzą w grę, a on jest dziś jedynym zmierzonym kandydatem. Koszt porównywalny
z najtańszym chmurowym (~$4 za korpus), rozdzielczość `component` najlepsza w zestawie, ale dzieli
z połową stawki wadę `cause` i ma najkrótsze `solution`.

## Cena i czas

| miara | haiku 4.5 | sonnet 5 | gpt-4.1-mini | gpt-4.1 | gpt-5.4-mini | gpt-5.4 | o4-mini | bielik-11b |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stawka wejścia (za 1M) | $1,00 | $3,00 | $0,40 | $2,00 | $0,75 | $2,50 | $1,10 | **—** |
| Stawka wyjścia (za 1M) | $5,00 | $15,00 | $1,60 | $8,00 | $4,50 | $15,00 | $4,40 | **—** |
| Koszt próbki | $0,069 | $0,287 | $0,023 | $0,119 | $0,045 | $0,158 | $0,103 | **$0** |
| Średnio na zgłoszenie | $0,0069 | $0,0287 | $0,0023 | $0,0119 | $0,0045 | $0,0158 | $0,0103 | **$0** |
| Koszt 33319 *(25 komentarzy)* | $0,038 | $0,187 | $0,014 | $0,069 | $0,026 | $0,082 | $0,042 | *nie przeszło* |
| Czas 33319 | 5,8 s | 42 s | 9,5 s | 16,4 s | 3,3 s | 2,3 s | 11,9 s | *nie przeszło* |
| Czas próbki | — | — | — | — | — | — | — | **2 min 26 s** |
| Tokeny wyjścia (próbka) | ~3 600 * | ~8 900 * | 1 841 | 2 037 | 2 028 | 2 003 | **10 971** | 6 956 |
| Ekstrapolacja na korpus | ~$10 | ~$43 | ~$3,5 | ~$18 | ~$7 | ~$24 | ~$15 | **$0 + GPU** |

Bielik nie ma stawki za token, bo działa na własnym sprzęcie. Koszt przebiegu to **czas GPU**:
RTX 4090 na RunPodzie $0,69/h, a próbka dziewięciu zgłoszeń zajęła 2 min 26 s (~15 s na zgłoszenie).
Ekstrapolacja na korpus 1500 zgłoszeń: **~6 h GPU ≈ $4** — czyli w okolicach `gpt-4.1-mini` (~$3,5),
przy czym cały koszt jest z góry przewidywalny i nie zależy od długości wątków.

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

Bielik liczony z **dziewięciu** rekordów, nie dziesięciu — udziały podane w tej samej skali
(np. „5/9"), żeby kolumny dało się czytać obok siebie.

| miara | chat *(odniesienie)* | haiku | sonnet | gpt-4.1-mini | gpt-4.1 | gpt-5.4-mini | gpt-5.4 | o4-mini | bielik-11b |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Zgodnych z `ParsedTicket` | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | **9/10** |
| Różnych wartości `component` | 2 | 6 | 1 | 1 | 1 | 1 | 5 | 1 | 2 |
| Rozpoznał ePUAP tam, gdzie chat *(24506, 34287)* | 2/2 | 2/2 | 0/2 | 0/2 | 0/2 | 0/2 | **2/2** | 0/2 | **2/2** |
| `resolution = naprawione` | 3 | 2 | 2 | 3 | 3 | 3 | 2 | 1 | 2 |
| `resolution = bez_zmian_w_systemie` | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | **4** |
| Puste `solution` | 5/10 | 7/10 | 7/10 | 6/10 | 6/10 | 6/10 | 6/10 | **9/10** | 5/9 |
| Puste `cause` | 9/10 | 9/10 | 10/10 | 10/10 | 10/10 | 9/10 | 10/10 | 9/10 | **7/9** |
| Puste `questions_summary` | 8/10 | 9/10 | 8/10 | 8/10 | 9/10 | 7/10 | 8/10 | 7/10 | **0/9** |
| Śr. długość `solution` (znaki) | 355 | 203 | 293 | 322 | **364** | 266 | 256 | 247 | **154** |
| Śr. długość `questions_summary` | 255 | 317 | 166 | 120 | 207 | 233 | 179 | 187 | 89 |
| Znalezione `error_codes` | 1 | 0 | 0 | 1 | 1 | 0 | 1 | 0 | 0 |

Rozproszenie `component` znaczy co innego u każdego z modeli, które je mają. U `haiku` to bałagan
(`eSOD` i `ESOD` obok siebie, `serwer DOKUS`, `usługa ePUAP`) — przy 1500 wywołaniach pole byłoby
bezużyteczne. U `gpt-5.4` i `bielik-11b` to **rozdzielczość**: trafiony `ePUAP` dokładnie w tych
zgłoszeniach, w których rozpoznał go chat. Pozostałe modele spłaszczają wszystko do
`główna aplikacja` i **tracą to rozróżnienie**.

Dwie skrajności Bielika wymagają komentarza, bo wyglądają jak zalety, a nie są nimi w całości:

- **`questions_summary` wypełnione w 9/9** — jedyny taki wynik w zestawie (reszta: 1–3 na 10). Ale
  przy 33644 wpisał tam *„Brak pytań dotyczących konfiguracji lub działania systemu"*, czyli zdanie
  o braku danych zamiast jawnego `brak`. To **obejście jawnego wyjścia ze schematu**, a nie
  wypełnione pole — przy masowym przebiegu dałoby korpus pozornie bogaty w pytania.
- **`bez_zmian_w_systemie` w 4/9** — najwyższy udział w zestawie (reszta: 0–1). Model chętniej
  przypisuje klasę rozstrzygnięcia niż zostawia `brak`, co przy niepewnych wątkach jest ryzykiem.

## Ocena merytoryczna

**Skala 1–5:** 5 = wzorcowo · 4 = dobrze, drobne braki · 3 = poprawnie, bez wartości dodanej ·
2 = wada wymagająca poprawy promptu lub przebiegu · 1 = wada dyskwalifikująca.
Każda pozycja sprawdzona wobec wątku źródłowego.

| kryterium | chat | haiku | sonnet | 4.1-mini | 4.1 | 5.4-mini | 5.4 | o4-mini | bielik-11b |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Niezmyślanie przyczyny (`cause`) | 5 | **1** | 5 | 5 | 5 | **2** | 5 | **1** | **2** |
| Zapis odrzuconej hipotezy | 5 | 2 | 4 | 2 | 3 | 3 | 4 | **1** | 4 |
| Rozstrzygnięcie z długiego wątku (33319) | **2** | 4 | 4 | 5 | 5 | 4 | **2** | **2** | *n/d* |
| Zgłoszenie informacyjne (33644) | 5 | 2 | 2 | 2 | **5** | 2 | **5** | 2 | 2 |
| Rozdzielczość `component` | 5 | **1** | 3 | 3 | 3 | 3 | **5** | 3 | **5** |
| Kompletność `solution` | 5 | 3 | 4 | 4 | 5 | 4 | 4 | **2** | **2** |
| Konkrety w `questions_summary` | 5 | 3 | 3 | 3 | 3 | **5** | 3 | 3 | **2** |
| Zgodność z zasadą 9 | 5 | **1** | 5 | 5 | 5 | **2** | 5 | **1** | **2** |
| **Przydatność do przebiegu** | n/d | **1** | 4 | 3 | 4 | **2** | **5** | **1** | **2** |

Uzasadnienia ocen krytycznych:

| model | co się stało |
|---|---|
| `haiku` | w 11312 wpisał do `cause` „problem prawdopodobnie wynika z infrastruktury sieciowej" — hipotezę obaloną w tym samym wątku, jako ustaloną przyczynę |
| `gpt-5.4-mini` | ta sama wada w łagodniejszej formie: `cause` = „Prawdopodobnie problemy z infrastrukturą sieciową"; słowo „prawdopodobnie" nie ratuje pola, które ma nieść przyczynę ustaloną |
| `o4-mini` | najgorszy wariant tej wady: `cause` = „Problemy z infrastrukturą sieciową" **bez cienia zastrzeżenia**, przy `solution = brak` — zostaje sama zmyślona przyczyna, bez kontekstu, który by ją podważał. Do tego 9/10 pustych `solution` |
| `chat`, `gpt-5.4`, `o4-mini` przy 33319 | zgubiły rozstrzygnięcie w najdłuższym wątku (`resolution = brak`), mimo że wątek kończy się potwierdzeniem naprawy |
| `gpt-4.1`, `gpt-5.4` przy 33644 | **jedyne poza czatem** ocaliły treść zgłoszenia informacyjnego (wykaz zmian wersji); pozostałe wyrzuciły wszystko |
| `bielik-11b` — `cause` | ta sama wada co u trzech pozostałych: w 11312 wpisał „Prawdopodobnie problemy z infrastrukturą sieciową" jako przyczynę. Łagodzi ją tym, że w tym samym polu **zapisał odrzuconą hipotezę** („podejrzewano niski poziom miejsca na dysku, ale przeniesienie logów nie rozwiązało problemu") — czego `haiku` i `o4-mini` nie zrobiły |
| `bielik-11b` — `questions_summary` | wypełnione w **9/9**, ale częściowo pozornie: przy 33644 wpisał „Brak pytań dotyczących konfiguracji…" zamiast `brak` (obejście jawnego wyjścia ze schematu), a przy 27298 pytanie **proceduralne** („czy system działa teraz poprawnie"), którego prompt zakazuje |
| `bielik-11b` — `solution` | średnio **154 znaki**, najmniej w zestawie (reszta: 203–364). Streszcza tam, gdzie inne modele przenoszą krok po kroku — przy zastrzeżeniach z korpusu to realna strata treści |
| `gpt-5.4-mini` przy 11312 | **jedyny** wyłowił pytania diagnostyczne z wątku; `sonnet`, `gpt-5.4` i `o4-mini` wpisały tam pytanie proceduralne, którego prompt zakazuje |

## Wnioski

| # | wniosek | konsekwencja |
|---|---|---|
| 1 | Zmyślanie przyczyny nie jest wadą jednego modelu ani jednej rodziny | powtórzyły je **4 z 8** modeli, u obu dostawców chmurowych i w modelu lokalnym, na każdym poziomie cenowym — to **luka promptu**, nie własność dostawcy |
| 2 | Rozdzielczość `component`: tylko dwa modele ją mają | `gpt-5.4` i `bielik-11b` trafiły `ePUAP` tam, gdzie chat; pozostałe spłaszczają do `główna aplikacja`, tracąc rozróżnienie bez zostawiania śladu |
| 3 | Model rozumujący nie pomógł | `o4-mini` ma najgorszy wynik merytoryczny w zestawie przy 5× większym zużyciu tokenów wyjścia — rozumowanie poszło w koszt, nie w jakość |
| 4 | Cena nie przewiduje jakości | `gpt-4.1-mini` (najtańszy z chmurowych, ~$3,5 za korpus) wypada lepiej niż `gpt-5.4-mini` i `o4-mini`, bo nie zmyśla przyczyny |
| 5 | **Luka promptu:** zgłoszenia informacyjne | 6 z 9 wariantów wyrzuciło całą treść 33644; CLAUDE.md liczy ~40 takich rekordów („dokumentacja, nie incydent") — do rozstrzygnięcia przed etapem 10 |
| 6 | **Luka promptu:** zakaz pytań proceduralnych działa słabo | 4 modele mimo zakazu wpisały pytanie w rodzaju „czy po zmianie jest lepiej" do `questions_summary` |
| 7 | Limity szybkości zatrzymają przebieg na korpusie | `gpt-4.1` dostał HTTP 429 przy dziesiątym zgłoszeniu; wznawianie po identyfikatorach jest wymogiem etapu 10, nie udogodnieniem |
| 8 | Model lokalny jest konkurencyjny kosztem, nie jakością | Bielik na własnym GPU wychodzi ~$4 za korpus (czas RTX 4090), czyli w okolicach najtańszego modelu chmurowego — ale ma najkrótsze `solution` w zestawie i tę samą wadę `cause` |

## Bielik: osobne warunki pomiaru

Kolumny Bielika **nie są w pełni porównywalne** z resztą tabeli i trzeba o tym wiedzieć przed
wyciąganiem wniosków:

| różnica | skutek |
|---|---|
| **9 zgłoszeń zamiast 10** | zgłoszenie 33319 (87 tys. zn.) nie zmieściło się w oknie kontekstu serwera; wszystkie udziały liczone z dziewięciu |
| **Okno serwera mniejsze niż deklarowane** | model deklaruje 32K, `OLLAMA_CONTEXT_LENGTH` ustawiono na 32768, ale realne okno wyniosło **16384** — Ollama zredukowała je, bo model zajął 18,7 GB z 24 GB VRAM. Zmierzone, nie odczytane z konfiguracji |
| **Kwantyzacja Q8_0, nie pełna precyzja** | wagi skwantyzowane do 8 bitów (12 GB zamiast 22 GB); wariant `bf16` mógłby dać inny wynik |
| **Modelfile wymusza `temperature 0.1`** | nasze `temperature=0` z żądania ma wyższy priorytet i wygrywa, ale to kolejne miejsce, gdzie ustawienie serwera może przebić konfigurację |

Pierwsza pozycja odsłoniła realną lukę w naszym kodzie: dwa z trzech zabezpieczeń przed ucięciem
mierzą wobec `LLM_NUM_CTX`, więc przy **źle skonfigurowanym oknie oba milczą**. Artefakt uratowała
wtedy dopiero walidacja JSON-a — przypadkiem, bo ucięcie usunęło całą treść zgłoszenia i model
odpowiedział zdaniem zamiast strukturą. Dołożone po tym trzecie zabezpieczenie porównuje **znaki
wysłane z tokenami zaraportowanymi** (zmierzone: 1,3 przy poprawnych wywołaniach, 5,6 przy
uciętym) i jako jedyne nie zależy od konfiguracji.

## Rekomendacja

Punktacja składa trzy tabele w jedną liczbę. **Reguły przeliczania są jawne**, żeby wynik dało się
sprawdzić i zakwestionować — bez nich „punkty" byłyby oceną autora przebraną za arytmetykę.

| składowa | waga | źródło | jak liczona |
|---|---:|---|---|
| Jakość | 40% | średnia ocen merytorycznych (bez wiersza zbiorczego) | skala 1–5 przeskalowana na 0–100 |
| Cena | 40% | koszt korpusu z tabeli cenowej | najtańszy = 100, najdroższy = 0, reszta liniowo |
| Czas | 20% | średni czas na zgłoszenie | najszybszy = 100, najwolniejszy = 0, reszta liniowo |

**Kara za łamanie zasady 9, zamiast wykluczenia.** Ocena za *niezmyślanie przyczyny* mnoży wynik
końcowy: **1 → ×0,50**, **2 → ×0,75**, od 3 w górę bez kary. Powód takiej konstrukcji: samo
uśrednianie pozwala nadrobić taniością wadę, którą zasada 9 traktuje jako dyskwalifikującą
(`gpt-5.4-mini` wychodził wtedy na drugie miejsce), ale **próg wykluczający ukrywa informację** —
model z tą wadą nadal może być jedynym wyborem w danym kontekście. Mnożnik pokazuje jedno i drugie:
gdzie model stoi i ile go ta wada kosztuje.

| # | model | **punkty** | *bez kary* | kara | jakość | cena | czas | śr. ocen | koszt korpusu |
|---|---|---:|---:|:---:|---:|---:|---:|---:|---:|
| 1 | `gpt-4.1-mini` | **85,1** | 85,1 | — | 65,6 | 100,0 | 94,1 | 3,62 | ~$3,5 |
| 2 | `gpt-4.1` | **73,2** | 73,2 | — | 81,2 | 63,3 | 77,0 | 4,25 | ~$18 |
| 3 | `gpt-5.4` | **69,1** | 69,1 | — | 78,1 | 48,1 | 93,3 | 4,12 | ~$24 |
| 4 | `gpt-5.4-mini` | **58,3** | 77,7 | ×0,75 | 53,1 | 91,1 | 100,0 | 3,12 | ~$7 |
| 5 | `bielik-11b` *(self-hosted)* | **42,5** | 56,6 | ×0,75 | 42,9 | 98,7 | 0,0 | 2,71 | ~$4 |
| 6 | `sonnet 5` | **32,0** | 32,0 | — | 68,8 | 0,0 | 22,2 | 3,75 | ~$43 |
| 7 | `haiku 4.5` | **32,0** | 63,9 | ×0,50 | 28,1 | 83,5 | 96,3 | 2,12 | ~$10 |
| 8 | `o4-mini` | **23,4** | 46,7 | ×0,50 | 21,9 | 70,9 | 48,1 | 1,88 | ~$15 |

Kolumna *bez kary* jest w tabeli celowo — pokazuje, że `haiku` (63,9) i `gpt-5.4-mini` (77,7) są
same w sobie mocnymi kandydatami i **traci je wyłącznie jedno kryterium**. Gdyby prompt domknął
lukę `cause` (wniosek 1), oba wróciłyby do czołówki.

**Dwie kolumny Bielika trzeba czytać z zastrzeżeniem.** Cena (98,7) porównuje czas GPU ze stawką za
tokeny — to inna jednostka kosztu sprowadzona do wspólnej skali dolarowej, więc rząd wielkości jest
wiarygodny, ale nie druga cyfra znacząca. Czas (0,0) wynika z 15 s na zgłoszenie wobec 1,5 s
u najszybszego — realna różnica, ale bez sensu operacyjnego przy przebiegu, który i tak trwa
godziny w tle. Jakość (42,9) liczona z **siedmiu** kryteriów zamiast ośmiu, bo 33319 wypadło.

Czego sam ranking nie pokazuje:

- **Zwycięzca wygrywa ceną, nie jakością** — `gpt-4.1-mini` ma trzecią jakość w stawce (3,62), ale
  jest 5× tańszy od `gpt-4.1`. Przy wadze ceny 40% to przesądza. Gdyby jakość ważyła 60%, pierwsze
  miejsce zająłby `gpt-4.1`.
- **`sonnet 5` i `haiku 4.5` mają identyczne 32,0 z przeciwnych powodów** — Sonnet za cenę (zero
  punktów, najdroższy w zestawie) przy dobrej jakości, Haiku za jakość obciętą karą przy dobrej
  cenie. Ta sama liczba, dwie różne decyzje do podjęcia.
- **Miejsca 2 i 3 dzielą 4 punkty** — mało jak na tak różny koszt ($18 vs $24). Rozstrzygają
  kryteria spoza punktacji: `gpt-5.4` trafia `component` (razem z Bielikiem, jako jedyne dwa),
  `gpt-4.1` ma wyższą średnią ocen i ratuje zgłoszenia informacyjne.
- **Ranking mierzy przydatność do parsowania korpusu, nie do każdego zastosowania.** Model
  self-hosted odpowiada na pytanie, którego ta skala nie zadaje — patrz niżej.

## Kategoria osobna: model self-hosted

Gdy dane nie mogą wyjść na zewnątrz, wybór nie brzmi „Bielik czy `gpt-4.1-mini`", tylko „Bielik czy
rezygnacja z parsowania". W tej kategorii **`bielik-11b` jest dziś jedynym zmierzonym kandydatem**
i wypada użytecznie:

| miara | `bielik-11b` | najlepszy chmurowy *(dla skali)* |
|---|---|---|
| Koszt korpusu | **~$4** (6 h RTX 4090) | ~$3,5 (`gpt-4.1-mini`) |
| Dane opuszczają infrastrukturę | **nie** | tak |
| Rozdzielczość `component` | **5/5** — trafia `ePUAP` jak chat | 3/5 |
| `questions_summary` wypełnione | **9/9** | 1–3 na 10 |
| Zmyślanie przyczyny (`cause`) | **2/5** — wada wspólna z 3 modelami chmurowymi | 5/5 |
| Kompletność `solution` | **2/5** — śr. 154 zn., najmniej w zestawie | 4/5 |

**Werdykt dla tej kategorii: nadaje się, pod dwoma warunkami.** Po pierwsze, luka `cause` musi
zostać domknięta w prompcie — a to i tak konieczne, bo dotyczy połowy zestawu, nie tylko Bielika
(wniosek 1). Po drugie, krótkie `solution` wymaga sprawdzenia, czy przy zastrzeżeniach z korpusu
nie gubi treści — to pomiar do wykonania przed masowym przebiegiem.

**Ograniczenie okna kosztuje mniej, niż wyglądało — zmierzone na całym korpusie.** Przy oknie
16384 (limit ~44,6 tys. znaków) z 1825 zgłoszeń odpada **jedno: 0,1%**. Mediana wątku to 5,7 tys.
znaków, p95 — 7,7 tys.; zgłoszenie 33319 (92 tys. zn.) jest odosobnionym wyjątkiem, nie czubkiem
rozkładu. Przy pełnym oknie 32768 nie odpada żadne.

Odwrotna strona tej liczby: **próbka kontrolna była dobrana pod skrajności**, więc jedno zgłoszenie
na dziesięć przekroczyło limit (10%), podczas gdy w korpusie to 0,1%. Kolumna „9/10" u Bielika
przecenia więc ten problem stukrotnie.

**Czego ten pomiar NIE rozstrzyga:** wynik pochodzi z kwantyzacji Q8_0 przy oknie zredukowanym do
16384 (brak VRAM na karcie 24 GB). Wariant `bf16` albo większa karta mogą dać inny rezultat —
zwłaszcza dla `cause` i `solution`, gdzie Bielik wypadł najsłabiej.
- **Sonnet 5 przegrywa podwójnie** — najdroższy i najwolniejszy w zestawie, przy jakości niższej niż
  oba modele `gpt-4.1`. Zero punktów w dwóch składowych to nie kara za mało — to skutek skalowania
  do skrajności zestawu.

**Wybór zależy od tego, co jest ograniczeniem.** Budżet → `gpt-4.1-mini`. Jakość artefaktu, którego
nie da się przeparsować bez ponownego kosztu (zasada 7) → `gpt-4.1` albo `gpt-5.4`.
