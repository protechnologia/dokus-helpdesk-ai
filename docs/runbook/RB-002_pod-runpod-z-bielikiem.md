# RB-002: Pod na RunPodzie z Bielikiem dla anonimizatora

## Cel

Działający model anonimizujący usługi `anonymizer`: pod z vLLM i Bielikiem 11B v3 utworzony
z szablonu, jego adres w `LLM_ANONYMIZATION_BASE_URL` i usługa, która przez niego anonimizuje.
Pod powstaje na sesję pracy i jest usuwany po niej (decyzja 2026-10-23), więc każdy ma nowe id
i nowy adres.

## Kiedy

Przed pracą, która woła prawdziwy model anonimizujący: trasy grafów przy prawdziwym modelu
generującym, masowy import zgłoszeń, testy `llm_live` anonimizatora, pokaz. Bez poda usługa
wstaje, a trasy grafów oddają 503.

## Wymaga

- Klucz API RunPoda w `~/.runpod/api_key` (chmod 600), nigdy w `.env*` projektu. Uprawnienia:
  Restricted, `api.runpod.io/graphql` Read / Write, `api.runpod.ai` None — wystarczają na
  REST v2.
- Id szablonu „vLLM Bielik 11B v3.0 AWQ 16k” w `~/.runpod/template_id`; szablon jest prywatny,
  na koncie, a id widać w konsoli RunPoda (Templates).
- Stack z usługą `anonymizer` na silniku `agent` (`ANONYMIZATION_ENGINE=agent`)
  i z `LLM_ANONYMIZATION_MODEL=speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic` w `.env`.

## Koszt

- RTX 4090 w SECURE: 0,89 USD/h (2026-10-23), od utworzenia poda do `terminate`.
- Wolumen 30 GB z szablonu: 0,10 USD/GB/mies. w trakcie pracy, 0,20 USD/GB/mies. przy
  zatrzymanym podzie (6 USD/mies.); `terminate` go kasuje.
- Utworzenie, start i `terminate` to płatne GPU albo utrata dysku: agent pyta przed każdym.
  Odczyt stanu (lista podów, `/v1/models`) jest bez pytania.

## Kroki

1. **Utwórz poda z szablonu — płatne, zapytaj przed.** Odpowiedź niesie `env` szablonu, więc
   filtr go zdejmuje:

   ```bash
   curl -s -X POST https://api.runpod.io/v2/pods \
     -H "Authorization: Bearer $(cat ~/.runpod/api_key)" -H "Content-Type: application/json" \
     -d "{\"name\":\"bielik-anonymizer\",\"templateId\":\"$(cat ~/.runpod/template_id)\",\"gpu\":{\"id\":\"NVIDIA GeForce RTX 4090\",\"count\":1},\"cloud\":\"SECURE\"}" \
     | python3 -c "import json,sys; d=json.load(sys.stdin); d.pop('env',None); print({k: d[k] for k in ('id','desiredStatus','costPerHr') if k in d} or d)"
   ```

   Wynik: słownik z `id` poda (HTTP 201). Odpowiedź 400 „There are no
   longer any instances available…” to chwilowy brak maszyny: ponów to samo polecenie po chwili
   (bywa kilkanaście prób co 30 s).
2. **Ustaw adres poda:** `POD=<id poda>` i `BASE=https://$POD-8000.proxy.runpod.net/v1`.
3. **Poczekaj na model**, ponawiając co 10 s, aż odpowie 200:
   `curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 $BASE/models`. W pierwszej próbie
   (2026-10-23) model odpowiedział po 78 s.
4. **Krótki czat** — odpowiedź w sekundę:

   ```bash
   curl -s $BASE/chat/completions -H "Content-Type: application/json" \
     -d '{"model":"speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic","messages":[{"role":"user","content":"Odpowiedz jednym słowem: działasz?"}],"max_tokens":5}'
   ```

5. **Wpisz adres do `.env`** i do każdej lokalnej kopii, z której `.env` bywa przepisywany
   (u nas `.env.dev.*`), inaczej po zmianie dostawcy wraca stary adres:
   `sed -i "s#^LLM_ANONYMIZATION_BASE_URL=.*#LLM_ANONYMIZATION_BASE_URL=$BASE#" .env .env.dev.*`.
   Sprawdź wynik interpolacji, nie plik:
   `docker compose config | grep LLM_ANONYMIZATION_BASE_URL`.
6. **Odtwórz usługę z nowym adresem:** `docker compose up -d anonymizer`; zaczekaj na
   `(healthy)` w `docker compose ps anonymizer`.

## Weryfikacja

- `curl -s localhost:8002/info` oddaje `{"engine":"agent","model":"speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic"}`
  (port to `DOCKER_ANONYMIZER_PORT`, domyślnie 8002).
- `curl -s -X POST localhost:8002/anonymize -H 'Content-Type: application/json' -d '{"text":"Jan Nowak zgłasza, że przesyłki nie przychodzą."}'`
  oddaje tekst ze znacznikami zamiast osoby i `"engine":"agent"`.

## Sprzątanie

- **Po pracy usuń poda — nieodwracalne, kasuje dysk z wagami; zapytaj przed:**

  ```bash
  curl -s -X POST https://api.runpod.io/v2/pods/$POD/action \
    -H "Authorization: Bearer $(cat ~/.runpod/api_key)" -H "Content-Type: application/json" \
    -d '{"action":"terminate"}' -w 'HTTP %{http_code}\n'
  ```

  Potem lista podów na koncie ma być pusta:
  `curl -s https://api.runpod.io/v2/pods -H "Authorization: Bearer $(cat ~/.runpod/api_key)"`.
- Zamiast `terminate` można dać `{"action":"stop"}`: id i adres zostają, wagi też, a płaci się
  tylko wolumen. Ryzyko: przy `start` maszyna z wolumenem może nie mieć wolnego GPU („zero
  GPUs”), wtedy zostaje `terminate` i nowy pod z nowym adresem.

## Pułapki

- Katalog dostępności (`GET /v2/catalog/gpus?include=AVAILABILITY&product=POD&cloud=SECURE`)
  nie jest wyrocznią: pokazał RTX 4090 jako `NONE`, a pody powstały. Przy 400 ponawia się to
  samo żądanie albo bierze inne GPU; szablonu ani wolumenu się nie zmienia.
- Tylko REST v2 (`api.runpod.io/v2`); REST v1 (`rest.runpod.io/v1`) wyłączono 2026-11-15.
- Pod tworzymy przez API, bo API dokłada wolumen 30 GB z szablonu samo, a nowa konsola RunPoda
  go nie przenosi („Nothing mounted at the template's path”).
- Szablon ma w nazwie „AWQ”, a model to `speakleash/Bielik-11B-v3.0-Instruct-FP8-Dynamic`
  z `--max-model-len 16384`, czyli `LLM_ANONYMIZATION_NUM_CTX`.
- Serwer z szablonu nie sprawdza klucza, więc `LLM_ANONYMIZATION_API_KEY` zostaje pusty. Ta
  zmienna idzie do serwera modelu w nagłówku: nie wpisuje się tam klucza dostawcy
  komercyjnego.
- Tworzenie z ponawianiem i czekanie na model piszemy dziś pętlą w powłoce przy każdym podzie;
  to kandydat na skrypt w `scripts/`.

## Powiązania

- [CLAUDE.md, „Usługa `anonymizer`”](../../CLAUDE.md#usługa-anonymizer): silnik `agent`
  i klient modelu anonimizującego.
- [CLAUDE.md, „Konfiguracja i deploy”](../../CLAUDE.md#konfiguracja-i-deploy): pułapki
  `LLM_ANONYMIZATION_*` i weryfikacja przez `docker compose config`.
- [`.env.example`](../../.env.example): zmienne `LLM_ANONYMIZATION_*` z opisem.

## Log

Najnowszy wpis na górze.

- 2026-11-25 — runbook spisany z notatek agenta i z zapisów przejść z 2026-10-23 – 2026-11-20;
  id szablonu przeniesione do `~/.runpod/template_id`.
- 2026-11-20 — przy imporcie kanału „Automat mailowy”: utworzenie z ponawianiem, adres w `.env`
  i `.env.dev.*`, `/info` i `/anonymize`, po pracy `terminate`.
- 2026-11-15 — przy wątkach golden setu po anonimizacji: utworzenie w pętli ponawiania (do 20
  prób co 30 s), po pracy `terminate`.
- 2026-10-23 — pierwsze przejście: rano dwa razy 400 „no instances”, pół godziny później siedem
  wariantów specyfikacji dało 201 w każdym; `/v1/models` po 78 s, czat 0,76 s.
