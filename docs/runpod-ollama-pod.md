# Pod z Ollamą na RunPodzie — ściągawka

Jak w kilka minut postawić GPU z modelem lokalnym (Bielik) wystawionym po HTTP, żeby nasze CLI
mogło do niego mówić bez zmian w kodzie. Sprawdzone 2026-08-02 na Bieliku 11B v3.0 Q8_0.

## 1. Instancja

| pole | wartość | dlaczego |
|---|---|---|
| GPU | **RTX 4090 (24 GB)** ~$0,69/h | karta docelowa wg CLAUDE.md; Bielik 11B Q8_0 to 12 GB wag |
| Szablon | **Ollama NVIDIA CUDA** (`ollama/ollama:latest`) | gotowy z listy RunPoda, nie trzeba budować własnego |
| Tryb | **On-Demand** | serverless ma zimny start na 12 GB — przy przebiegu wsadowym drożej i wolniej |

Nie bierz H100 ani RTX PRO 6000 — model wykorzysta ~20% ich pamięci, a stawka jest 3–4× wyższa.

## 2. Szablon (przycisk „Edit" → Pod template overrides)

| pole | wartość |
|---|---|
| Container disk | 20 GB |
| Volume disk | 30 GB |
| Volume mount path | `/workspace` |
| Expose HTTP ports | `11434` |
| Expose TCP ports | `22` |

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

Trzy rzeczy, których nie da się założyć — każda potrafi zepsuć cały przebieg:

```bash
# a) czy okno kontekstu naprawdę wynosi tyle, ile ustawiono
#    wyślij prompt na ~20 tys. tokenów i odczytaj usage.prompt_tokens z odpowiedzi
#    jeśli wróci ~2048 lub ~4096 — OLLAMA_CONTEXT_LENGTH nie zadziałało

# b) czy model w ogóle odpowiada i ile trwa jedno wywołanie
curl -s -X POST "$U/v1/chat/completions" -H "Content-Type: application/json" \
  -d '{"model":"...","messages":[{"role":"user","content":"Napisz OK"}],
       "max_completion_tokens":20,"temperature":0}'

# c) czy proxy wytrzyma długą odpowiedź bez zerwania połączenia
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
- **Weryfikuj okno pomiarem, nie konfiguracją.** Test rozstrzygający wymaga promptu **wielokrotnie
  dłuższego** niż podejrzewane okno — prompt zbliżony rozmiarem do okna nie odróżnia „parametr
  zadziałał" od „i tak się mieściło". Na tym poślizgnął się pierwszy test lokalny.
- **Modelfile Bielika wymusza `temperature 0.1`.** Wartość z żądania ma wyższy priorytet, więc
  nasze `temperature=0` wygrywa — warto jednak pamiętać przy porównaniach.
- **Tag `:latest` obrazu** kłóci się z regułą projektu „obrazy pinowane tagiem". Dla testu bez
  znaczenia; przy dłuższym użyciu szablonu podaj konkretną wersję.
- **Pod bez uwierzytelniania.** Adres proxy jest publiczny — każdy, kto go zna, może wysyłać
  zapytania na Twój koszt. Wyłączaj poda po przebiegu.

## Koszt

| pozycja | wartość |
|---|---|
| GPU | $0,69/h |
| Dysk przy działającym podzie | $0,007/h |
| Dysk przy zatrzymanym | $0,008/h |
| **Przebieg 10 zgłoszeń z pobraniem modelu i sondą** | **~$0,35** |
