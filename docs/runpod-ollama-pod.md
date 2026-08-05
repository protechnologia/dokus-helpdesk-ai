# Pod z Ollamą na RunPodzie — ściągawka

Jak w kilka minut postawić GPU z modelem lokalnym (Bielik) wystawionym po HTTP, żeby nasze CLI
mogło do niego mówić bez zmian w kodzie. Sprawdzone 2026-08-02 (RTX 4090) i **2026-08-05
(RTX A6000, przebieg 199 zgłoszeń)** na Bieliku 11B v3.0 Q8_0.

## 1. Instancja

| pole | wartość | dlaczego |
|---|---|---|
| GPU | **RTX A6000 (48 GB)** ~$0,79/h albo **RTX 4090 (24 GB)** ~$0,69/h | Bielik 11B Q8_0 to 12 GB wag, w VRAM zajmuje 15,3 GB |
| Tryb | **On-Demand** | serverless ma zimny start na 12 GB — przy przebiegu wsadowym drożej i wolniej |

**4090 bywa niedostępne** („No instances are currently available for this GPU type") — sprawdź
inne regiony, zanim zmienisz kartę, bo dostępność jest per region. Zamienniki w kolejności:
**A6000** (48 GB, zmierzona), **A5000** (24 GB, ~$0,45/h, wolniejsza o 30–40%).
Nie bierz H100 ani L40S — model wykorzysta ułamek ich pamięci przy 1,5–4× stawce.

**Uwaga: wolumen jest przypisany do regionu.** Pod w innym regionie startuje z pustym wolumenem,
czyli dochodzi ~3 min na pobranie wag.

## 2. Szablon (własny, „New Template" — albo „Edit" → Pod template overrides)

| pole | wartość |
|---|---|
| Template name | `ollama-a6000-ctx16k` |
| Container image | `ollama/ollama:0.32.5` |
| Container disk | 20 GB |
| Volume disk | 30 GB |
| Volume mount path | `/workspace` |
| Expose HTTP ports | `11434` (etykieta: `ollama-api`) |
| Expose TCP ports | `22` (etykieta: `ssh`) |
| Docker command | *(puste — obraz startuje `ollama serve` sam)* |

**Warto zrobić własny szablon**, bo gotowy „Ollama NVIDIA CUDA" z listy RunPoda nie ma dwóch
najważniejszych zmiennych (`OLLAMA_CONTEXT_LENGTH`, `OLLAMA_KEEP_ALIVE`) i trzeba je dopisywać
przy każdym nowym podzie. Szablon **nie zapamiętuje wag** — te siedzą na wolumenie, przypisanym
do poda, nie do szablonu.

**Nazwa niesie kartę i okno**, bo to jedyne dwie rzeczy, które ten szablon ustala ponad obraz —
i dzięki temu wariant na inną kartę albo inne okno da się od razu odróżnić na liście.

**Obraz pinowany tagiem**, nie `:latest` — szablon jest z definicji do wielokrotnego użytku,
więc ruchomy tag oznacza inną Ollamę niż ta, na której mierzono (reguła projektu o pinowaniu
obrazów).

**Wolumen musi zgadzać się ze zmienną `OLLAMA_MODELS`** — inaczej wagi lądują na dysku kontenera
i znikają przy restarcie. Szablon RunPoda montuje `/workspace` i ustawia `OLLAMA_MODELS` na
`/workspace/models`; alternatywnie zamontuj `/root/.ollama` i zmiennej nie ustawiaj wcale.

30 GB wystarcza na model docelowy plus dwa mniejsze do porównań (11B = 12 GB, 4.5B = 5 GB,
1.5B = 1,7 GB). Volume kosztuje też przy zatrzymanym podzie — nie bierz zapasu „na wszelki wypadek".

## 3. Zmienne środowiskowe

| zmienna | wartość | rola |
|---|---|---|
| `OLLAMA_HOST` | `0.0.0.0:11434` | bez tego serwer słucha tylko lokalnie i proxy go nie widzi |
| `OLLAMA_MODELS` | `/workspace/models` | katalog wag — musi leżeć na wolumenie |
| `OLLAMA_FLASH_ATTENTION` | `1` | liniowe zamiast kwadratowego zużycia pamięci przy długim kontekście |
| **`OLLAMA_CONTEXT_LENGTH`** | **`32768`** | **okno kontekstu — patrz niżej, to najważniejszy wpis** |
| **`OLLAMA_KEEP_ALIVE`** | **`-1`** | trzyma model w VRAM; bez tego po 5 min bezczynności wyładowuje 12 GB |

Pierwsze trzy szablon zwykle ma. **Dwie ostatnie trzeba dopisać ręcznie.**

## 4. Po starcie: pobranie modelu

```bash
U=https://<pod-id>-11434.proxy.runpod.net
curl -N -X POST "$U/api/pull" -H "Content-Type: application/json" \
  -d '{"model":"SpeakLeash/bielik-11b-v3.0-instruct:Q8_0","stream":true}'
```

11,9 GB schodzi w ~3 min. Weryfikacja:

```bash
curl -s "$U/api/tags"
```

## 5. Konfiguracja `.env` po naszej stronie

```
LLM_PROVIDER=ollama
LLM_BASE_URL=https://<pod-id>-11434.proxy.runpod.net/v1
LLM_MODEL=SpeakLeash/bielik-11b-v3.0-instruct:Q8_0
LLM_NUM_CTX=32768
LLM_MAX_OUTPUT_TOKENS=1500
LLM_TIMEOUT_SECONDS=900
```

Przy `LLM_NUM_CTX=32768` i budżecie odpowiedzi 1500 limit na prompt wychodzi **~93 tys. znaków** —
mieści całą próbkę kontrolną, łącznie ze zgłoszeniem 33319 (87 tys. zn.).

Sprawdzenie, że wszystko się spina:

```bash
helpdesk tickets parse data/parsed/bielik-11b -t 24506
```

## 6. Sonda przed przebiegiem (2 minuty, warto zawsze)

**Realne okno odczytaj z `/api/ps`, nie zgaduj z konfiguracji.** To najkrótsza droga i jedyna
pewna — pole `context_length` pokazuje, ile serwer FAKTYCZNIE przydzielił:

```bash
# 1. rozgrzewka — model wchodzi do VRAM dopiero przy pierwszym wywołaniu
curl -s -X POST "$U/v1/chat/completions" -H "Content-Type: application/json" \
  -d '{"model":"SpeakLeash/bielik-11b-v3.0-instruct:Q8_0",
       "messages":[{"role":"user","content":"Napisz OK"}],
       "max_completion_tokens":10,"temperature":0}'

# 2. odczyt realnego okna (i potwierdzenie, że KEEP_ALIVE działa)
curl -s "$U/api/ps"
```

W odpowiedzi liczą się trzy pola:
- **`context_length`** — realne okno; **to ono idzie do `LLM_NUM_CTX`**, nie wartość z ENV poda,
- **`expires_at`** — przy `OLLAMA_KEEP_ALIVE=-1` data jest absurdalnie odległa (rok 2318);
  data za 5 minut znaczy, że zmienna nie zadziałała i model będzie się przeładowywał,
- **`size_vram` = `size`** — cały model w VRAM, zero offloadu na CPU.

Uwaga: `/api/tags` też pokazuje `context_length`, ale **to jest deklaracja modelu z GGUF**
(32768 dla Bielika), nie to, co serwer przydzielił. Rozróżnienie jest istotne — na tym da się
pomylić przy pobieżnym sprawdzeniu.

Potem sonda przez nasze CLI, na jednym zgłoszeniu — sprawdza całą ścieżkę naraz
(`.env` → klient → pod → walidacja artefaktu):

```bash
helpdesk tickets parse data/parsed/<zestaw> -t 24506
```

## Pułapki (wszystkie napotkane 2026-08-02)

- **Cloudflare blokuje klienty inne niż przeglądarka i `curl`.** Python `urllib` dostaje
  `HTTP 403 error code: 1010` na `/api/pull`, podczas gdy `curl` przechodzi. Do pobrania modelu
  używaj `curl`; samo parsowanie idzie przez SDK OpenAI i działa normalnie.
- **Zaraz po starcie poda proxy zwraca 403 na kilka pierwszych żądań** — odczekaj kilkanaście
  sekund, zanim uznasz, że coś jest źle skonfigurowane.
- **`num_ctx` w treści żądania jest IGNOROWANY — zmierzone, nie domniemane.** Prompt na ~18 tys.
  tokenów przeszedł w całości przy żądaniu deklarującym okno 1024; identycznie w surowym JSON-ie
  (`options` na wierzchu) i przez `extra_body` w SDK. Okno ustawia **wyłącznie serwer**:
  `OLLAMA_CONTEXT_LENGTH`, a ponad nim `PARAMETER num_ctx` z Modelfile, jeśli model go ma.
  Konsekwencja dla nas: `LLM_NUM_CTX` w `.env` **niczego nie wymusza** — mówi tylko klientowi,
  jakie okno ma serwer, żeby mógł odrzucić za długie zgłoszenie. Ustawienie go **wyżej** niż
  realne okno serwera to cicha utrata końcówki wątku; łapie ją dopiero kontrola `prompt_tokens`
  po odpowiedzi.
- **Weryfikuj okno pomiarem, nie konfiguracją.** Najtaniej przez `/api/ps` (sekcja 6). Gdyby
  trzeba było sprawdzić promptem, musi być **wielokrotnie dłuższy** niż podejrzewane okno —
  prompt zbliżony rozmiarem nie odróżnia „parametr zadziałał" od „i tak się mieściło". Na tym
  poślizgnął się pierwszy test lokalny.
- **Większa karta NIE podnosi okna sama z siebie.** Przy 4090 okno spadło z 32768 do 16384
  z braku VRAM-u; przy A6000 (48 GB, model zajmuje 15,3 GB) ograniczenia pamięci nie ma, ale
  serwer i tak dał 16384 — bo tyle miał w `OLLAMA_CONTEXT_LENGTH`. **Ta sama liczba, inna
  przyczyna**: raz wymuszona, raz skonfigurowana. Nie zakładaj, że zmiana karty coś tu zmieni.
- **`curl` z przekierowaniem do pliku buforuje strumień.** `curl -N … | tee log` przy `/api/pull`
  nie pokazuje nic przez kilka minut, co wygląda jak zawieszone pobieranie. Postęp sprawdzisz
  osobnym, krótkim wywołaniem `/api/pull` — Ollama dopina się do trwającego pobierania i zwraca
  bieżący stan (`completed` / `total`), zamiast zaczynać od nowa.
- **Modelfile Bielika wymusza `temperature 0.1`.** Wartość z żądania ma wyższy priorytet, więc
  nasze `temperature=0` wygrywa — warto jednak pamiętać przy porównaniach.
- **Tag `:latest` obrazu** kłóci się z regułą projektu „obrazy pinowane tagiem". Dla testu bez
  znaczenia; przy dłuższym użyciu szablonu podaj konkretną wersję.
- **Pod bez uwierzytelniania.** Adres proxy jest publiczny — każdy, kto go zna, może wysyłać
  zapytania na Twój koszt. Wyłączaj poda po przebiegu.

## Koszt

| pozycja | wartość |
|---|---|
| GPU — RTX 4090 | $0,69/h |
| GPU — RTX A6000 | $0,79/h |
| Dysk przy działającym podzie | $0,007/h |
| Dysk przy zatrzymanym | $0,008/h |
| **Przebieg 10 zgłoszeń z pobraniem modelu i sondą** (4090) | **~$0,35** |
| **Przebieg 199 zgłoszeń** (A6000, 2026-08-05) | **~$0,29** + ~$0,05 pobranie modelu |

**Zmierzone tempo: ~6,5 s na zgłoszenie** (199 zgłoszeń w 21 min 42 s, 586k tokenów wejścia).
To ponad dwa razy szybciej niż 15 s z pierwszego pomiaru — tamta próbka była dobrana **pod
skrajności** (najdłuższe wątki w korpusie), więc jej średnia nie opisuje typowego przebiegu.
Pierwsze wywołanie po załadowaniu modelu trwa dłużej (8 s wobec ~5 s), potem `KEEP_ALIVE=-1`
trzyma wagi w VRAM.

Ekstrapolacja na pełny korpus (1408 rekordów po filtrze): **~2 h 30 min, ~$2**.
