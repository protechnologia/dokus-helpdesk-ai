# CLAUDE.md — [Nazwa projektu]

## Cel

[Co robi ta aplikacja]

## Zasady naczelne (NIE łamać bez wyraźnej decyzji)

1. **Konfiguracja wyłącznie przez ENV** (pydantic-settings) — żadnych sekretów ani
   endpointów na sztywno w kodzie.
2. **Komunikacja = REST (HTTP/JSON)** między komponentami.
3. **Modularność.** Każdy komponent = osobna usługa w `docker-compose`, którą da się podmienić
   lub zaktualizować **bez zmian w pozostałych** (i bez zmian w logice biznesowej).
4. **Abstrakcja dostawcy LLM** — logika nigdy nie rozmawia bezpośrednio z SDK dostawcy.
5. **Dev montuje kod z hosta** (zmiany żywe bez rebuildu); **prod kopiuje kod do obrazu** —
   uruchamiamy dokładnie tę wersję, którą zbudowaliśmy.
6. **Praca zawsze w izolowanym `venv`** — nigdy przeciw systemowemu Pythonowi. Przed każdą
   komendą Pythona (`pytest`/`ruff`/`pip`) `.venv` musi istnieć i być aktywny; jeśli go nie ma —
   najpierw utwórz i aktywuj.

## Stack

- Python, FastAPI, Pydantic, pydantic-settings
- Embeddingi: lokalny model PL — `OPI-PIB/PolDense-*` (rodzina 17M–1B; mały na dev/CPU,
  większy na prod/GPU). Wymiar wektora = konfiguracja kolekcji Qdrant.
- LLM: docelowo lokalny Bielik, podczas developmentu jakiś chmurowy dostawca
- DB: relacyjna MariaDB, wektorowa Qdrant
- Deploy: Docker Compose

## Don't (szybka lista czerwonych flag)

- **Nie importuj SDK dostawcy poza plikiem klienta**
- **Nie odpalaj testów na żywym LLM bez pytania**

## Praca z agentem

- **Prośba o plan = zostajesz w planowaniu.** „Jaki masz plan?" / „co proponujesz?" → przedstaw
  plan i **czekaj**. Odpowiedzi na pytania doprecyzowujące to NIE jest zgoda na implementację.
  - Bez zgody wolno: rozpoznanie — czytanie plików, `docker compose config`, sondy w scratchpadzie.
  - Dopiero po zgodzie: edycja plików projektu.
- **Commity bez trailerów współautorstwa** (`Co-Authored-By` itp.).
- Język komunikacji: polski.

## Commands

**Uruchomienie**
- Dev (kod montowany z hosta): `docker compose -f docker-compose.yml up -d`
- Prod (bez montowania): `docker compose -f docker-compose.prod.yml up -d`
- Po zmianie zależności lub `Dockerfile` (albo kodu na prodzie): `docker compose up -d --build <usługa>`
- Weryfikacja realnej konfiguracji: `docker compose config` (nie zawartość `.env`)

**Frontend**
- Dev: `npm run dev` w `frontend/` (proxy `/api` → FastAPI)
- Build → `api/app/static/`: `npm run build`

**Testy i jakość**
- Lint: `ruff check .`
- Jednostkowe (LLM = atrapa): `pytest`
- Integracyjne: `pytest -m integration_<usługa>` (albo parasol `pytest -m integration`)
- Na żywym LLM: `pytest -m llm_live` — **kosztuje / bije po sieci, pytaj przed**

**CLI / pakiet**
- `pip install -e .` — tylko po zmianie `pyproject.toml`, po zmianie kodu nigdy

## Podział na foldery i pliki

```
[projekt]/
├── docker-compose.yml            # baza — minimalny działający zestaw
├── docker-compose.<cel>.yml      # warstwy opcjonalne (patrz niżej)
├── .env                          # wartości lokalne — NIE w repo
├── .env.example                  # kontrakt konfiguracji — W repo
├── pyproject.toml                # pytest/lint + pakietowanie (entry-points CLI)
├── requirements-dev.txt          # zależności testów/lintera (poza obrazem)
├── CLAUDE.md / README.md
├── api/                          # folder = usługa z compose, nazwany tak samo
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── requirements.txt          # zależności RUNTIME tej usługi (do obrazu)
│   ├── scripts/                  # skrypty deweloperskie (python api/scripts/…)
│   └── app/                      # kod aplikacji
│       ├── cli/                  # CLI produkcyjne (Typer) — cienkie adaptery nad serwisami
│       ├── static/               # zbudowany frontend, serwowany przez FastAPI
│       ├── main.py               # montaż aplikacji, middleware, handlery wyjątków
│       ├── config.py             # Settings (pydantic-settings)
│       ├── models.py             # modele API (odrębne od domenowych)
│       ├── routers/              # jeden plik na zasób/endpoint, cienkie
│       │
│       │                         # --- nasza strona: podział po RODZAJU obiektu ---
│       ├── model/                # modele domenowe, JEDEN na plik
│       ├── service/              # logika: <rola>_<przedmiot>.py, zero modeli
│       ├── text/                 # treść czytana przez człowieka: prompty .md, słowniki .json
│       ├── util/                 # funkcje bezstanowe bez wiedzy o dziedzinie
│       │
│       │                         # --- za granicą procesu: pakiet na USŁUGĘ ---
│       ├── llm/                  # interfejs + implementacje + fabryka + modele transportu
│       └── <usługa>/             # tak samo dla każdej zewnętrznej usługi
├── frontend/                     # React (SPA) + Vite; build → api/app/static/
│   ├── src/
│   └── package.json
├── [tika]/                       # kolejna usługa: Dockerfile + jej konfiguracja
├── tests/
│   ├── unit/
│   └── integration/
├── integrations/<język>/         # klienci dla konsumentów API
└── samples/                      # dane wejściowe do testów i ewaluacji
```

- **Dwie osie podziału, granicą jest przekroczenie granicy procesu.** Co rozmawia z usługą
  zewnętrzną, dostaje **własny pakiet** (`llm/`, `embedding/`): interfejs, implementacje, fabryka,
  wyjątki i modele transportu razem, żeby podmiana dostawcy była zmianą jednego katalogu — dlatego
  te modele **nie wychodzą** do `model/`. Reszta idzie osią techniczną (`model` / `service` /
  `text` / `util`).
- **Folder = usługa z compose**; wszystko do zbudowania obrazu leży w nim, nie w korzeniu.
  Korzeń należy do infrastruktury: compose, `.env*`, dokumentacja, config testów.
- **Testy w korzeniu, nie w folderze usługi** — nie trafiają do obrazu, a integracyjne sięgają
  kilku usług. Ten sam plik może być w `unit/` i `integration/` (stąd `--import-mode=importlib`).
- **Pakiety usług nazwane rozłącznie** (`api/app/`, `embedder/embedder_app/`) — dwa pakiety `app`
  zasłaniają się w jednym procesie pytest. Niepakowana usługa dochodzi przez `pythonpath`
  w `pyproject.toml`.
- **Dwa pliki zależności:** `<usługa>/requirements.txt` = runtime, do obrazu;
  `requirements-dev.txt` w korzeniu = testy/lint, nigdy w obrazie.

## Warstwy kodu

- **Transport vs domena.** Transport = rozmowa z usługą zewnętrzną (Tika, LLM, baza); domena =
  logika, nieświadoma tego, co pod spodem. Domena dostaje klienta transportowego przez
  konstruktor, nigdy nie sięga po SDK.
- **Klient per usługa.** Jedna implementacja → klient tworzony wprost. Klient
  wymienny → z fabryki po configu (np. LLM: chmura na dev, Bielik na prod).
- **Handlery cienkie** — żądanie → serwis → odpowiedź; zero logiki i LLM w handlerze.
- **Osobne modele domenowe i API.** Encje/obiekty domeny nie wychodzą wprost przez HTTP —
  przepisujemy jawnie. Chroni kontrakt i blokuje wyciek pól wewnętrznych (ID, scoring).

- **Granica `model` / `service` działa w OBIE strony:** w `model/` wyłącznie modele, w `service/`
  ani jednego modelu. Model wychodzi z serwisu nawet wtedy, gdy używa go jeden serwis i zmienia
  się razem z nim. **Cena:** kilka importów więcej i rzeczy zmieniające się razem leżą osobno.
  **Wyjątek:** metoda czytająca własne pola zostaje na modelu, gdy jej jedyność jest
  zabezpieczeniem (np. sklejanie tekstu do embeddingu — dwa miejsca robiące to ręcznie
  rozjechałyby się bezgłośnie).
- **Nazwa pliku mówi, CO ROBI, nie czego dotyczy** — `validator_ticket_parsed.py`, nie
  `artifacts.py`. W `service/` oś `<rola>_<przedmiot>`, w `model/` prefiks tematyczny grupujący
  alfabetycznie (`ticket_raw`, `ticket_parsed`, `ticket_parse_result`).
- **Sprawdź nazwę przeciw wariantowi, który dojdzie później.** Jeśli dołożenie brata wymusi
  przemianowanie pierwszego, oś nazwy jest źle wybrana — zwykle znaczy to, że nazwa opisuje
  WYNIK, a pliki różni ŹRÓDŁO (albo odwrotnie).
- **Funkcja czy klasa — rozstrzyga stan, nie symetria.** Implementacja z cyklem życia (wagi
  modelu, sesja HTTP) to obiekt budowany raz; obliczenie bezstanowe zostaje funkcją modułową.
- **Katalog z samymi danymi potrzebuje `__init__.py`**, choć nikt go nie importuje:
  `[tool.setuptools.packages.find]` wykrywa pakiety po tym pliku, a bez niego treść wypada
  z dystrybucji i `FileNotFoundError` wychodzi dopiero w runtime. Napisz w tym pliku, po co jest —
  pusty `__init__.py` w katalogu bez kodu wygląda jak pozostałość do sprzątnięcia.

**Gdzie to położyć — cztery pytania, po kolei:**

1. **Rozmawia z usługą zewnętrzną?** → pakiet tej usługi (`llm/`, `embedding/`), razem z jej
   modelami transportu.
2. **Da się to opisać i przetestować, ani razu nie nazywając dziedziny?** → `util/`
   (strip HTML-a, formatowanie czasu, tłumaczenie błędu walidacji na tekst).
3. **Model danych czy operacja na nich?** → `model/` albo `service/`.
4. **Treść, którą człowiek czyta zdanie po zdaniu** (prompt, słownik pojęć)? → `text/`;
   kod, który ją składa — nigdy tam.
  
## Styl kodu

- Język kodu, identyfikatorów, docstringów i komentarzy: **angielski**.
- **Brak autoformattera — świadomie.** `ruff format`/`black` zjadłyby pionowe wyrównanie `=`
  (niżej). Używamy `ruff check` (linter), nie formattera.
- **Importy zawsze na górze modułu.** Lazy import tylko przy realnym problemie (cykl, faktycznie
  opcjonalna zależność albo **zmierzony** koszt ładowania) — nie „na wszelki wypadek". Konsekwencja
  przyjęta świadomie: import modułu pociąga jego zależności; przy zależnościach twardych to OK.
  Robiąc wyjątek, podaj w komentarzu liczbę, która go uzasadnia (patrz „Warstwa LLM").
- Type hints obowiązkowe w sygnaturach; zamiast nieotypowanego `dict` — model Pydantic
  lub `TypedDict`.
- **Nazwy opisują intencję** — `fetch_invoice_summary`, nie `get_data`.
- **Casing:** `snake_case` funkcje/zmienne, `PascalCase` klasy, `UPPER_CASE` stałe.
- **f-stringi** do formatowania, nie `%` ani `.format()`.
- **Wczesne wyjścia** (guard clauses) zamiast zagnieżdżonych `if/else`.
- **Bez martwego i zakomentowanego kodu** — kasuj, git pamięta.
- **Bez łapania gołego `Exception`** — konkretne typy.
- **Dekompozycja metod — wg testowalności, NIE wg długości.** Liczba linii nie jest metryką.
  Wydzielamy, gdy spełnione choć jedno kryterium:
  1. **Czystość/testowalność** — blok da się przetestować bez I/O (sieć, SDK, dysk).
  2. **Ponowne użycie.**
  3. **Zaciemnia główny przepływ.**
  Żadne z nich → **nie tnij** (rozbicie liniowego kodu wołanego raz to „ravioli code").
- **Metoda publiczna = orkiestrator.** Gdy klasa ma jedną główną metodę publiczną, trzyma ona
  przepływ na wysokim poziomie i deleguje do prywatnych helperów — czyta się ją jak spis kroków
  (zbuduj → wywołaj → zmapuj), a szczegóły siedzą w metodach prywatnych.
- **Pionowe wyrównanie `=`** w wieloliniowych blokach argumentów nazwanych i przypisań —
  nazwy dopełniane spacjami do najdłuższej w bloku:

  ```python
  metadata = Metadata(
      content_type    = meta.content_type,
      language        = meta.language,
      char_count      = meta.char_count,
      pages_processed = meta.pages_processed,
  )
  ```

## Warstwa CLI

Dwie kategorie, których nie mieszamy:
1. Deweloperskie — `api/scripts/*.py`, uruchamiane `python api/scripts/nazwa.py`.
2. Produkcyjne — `api/app/cli/cli.py`, jeden wpis w `[project.scripts]` na całe drzewo subkomend.

Wspólne:
- Framework: Typer.
- Wpis w `[project.scripts]` = osobna komenda (`myapp-worker`); `@cli.command()` = subkomenda (`myapp meters import`).
- `pip install -e .` tylko po zmianie pyproject.toml, po zmianie kodu nigdy.
- CLI to cienkie adaptery nad serwisami domenowymi (jak handlery HTTP) — zero logiki w komendzie.

### Gotchas

- **Tekst pomocy przez `help=`** — inaczej Typer wstawi do `--help` docstring pisany dla programisty.
- **`@cli.callback()` nawet przy jednej komendzie** — inaczej Typer zwija drzewo i odpala ją wprost.

## Warstwa API

- **`/health` mówi „ok" tylko o samym API** — o stanie zależności nie mówi nic.

## Warstwa LLM

- **Jeden plik importuje SDK dostawcy** — reszta kodu tylko przez `LLMClient` (zasada 4).
  Zmiana API komercyjne → model on-prem = zmiana konfiguracji/klienta, nie logiki.
- **Fabryka `get_llm_client()` po `LLM_PROVIDER`, fail-fast** — brak klucza/modelu/base_url →
  `LLMConfigError` przy budowie klienta, nie błąd połączenia w środku żądania.
- **SDK dostawców importuj LENIWIE, wewnątrz builderów** — świadomy wyjątek od „importy na górze".
  SDK modeli budują przy imporcie modele Pydantic całego swojego API (u nas: `anthropic` ~5,5 s,
  `openai` ~3,3 s), a fabryka importuje wszystkie klienty, żeby wybrać jednego — więc bez tego
  każdy proces płaci za biblioteki, których nie zawoła. Zysk dotyczy przebiegów **częściowych**
  (testy nietykające dostawcy, komendy CLI); tam, gdzie testy klientów importują SDK wprost, nie ma
  go wcale. Cena: buildery zwracają interfejs `LLMClient`, nie konkretną klasę.
- **Domyślnie `FakeLLMClient`** (offline) — `up` i `pytest` nic nie wysyłają i nic nie kosztują;
  realny dostawca włączany jawnie w ENV.
- **Endpoint zgodny z API OpenAI** (Ollama, vLLM, proxy) → model lokalny tym samym klientem,
  wystarczy `LLM_BASE_URL` + `LLM_MODEL`. Inny kształt API (Azure) → osobny klient, nie `if`
  w istniejącym.
- **Wywołania async z jawnym timeoutem.**
- **`temperature` z ENV** (domyślnie `0`).
- **Walidacja wyjścia:** parsuj do modelu Pydantic; błąd → **jeden** retry z feedbackiem, potem
  porażka (nie pętla).
- **Retry sieciowy tylko z backoffem i capem prób.**
- **Loguj każde wywołanie:** model, tokeny in/out, latencja, koszt (log strukturalny). Treści
  promptu/odpowiedzi **nigdy na INFO** (dane użytkownika) — tylko DEBUG.

### Gotchas

- **Ollama: okno kontekstu ustawia wyłącznie `OLLAMA_CONTEXT_LENGTH` na serwerze — `num_ctx`
  w żądaniu (także przez `extra_body` w SDK OpenAI) jest IGNOROWANY, a nadmiar ucinany BEZ BŁĘDU.**
  Artefakt z połowy wejścia wygląda na kompletny, więc klient musi odmówić za długiego wejścia
  przed wysłaniem i sprawdzić po odpowiedzi, czy `prompt_tokens` nie wypełniło całego okna.
  Nigdy nie przycinaj sam.

### Prompty

- **Prompt = logika, nie konfiguracja** — szablony w kodzie (`api/app/text/`, jeden plik na
  prompt), **nigdy w ENV**.
- **Treść promptu to dokument `.md`; kod, który go składa, mieszka w `service/`.** Prompt jest
  jedyną rzeczą, którą człowiek musi kontrolować zdanie po zdaniu — sklejany z kilku stałych
  czyta się przez składnię Pythona, a jako dokument pokazuje zmianę treści wprost w diffie.
  Dotyczy to także promptu systemowego. Komentarze redakcyjne (`<!-- … -->`) **wycinaj przed
  wysłaniem**: notatka dla nas nie ma prawa dotrzeć do modelu.
- **Każdy prompt ma test-strażnik** — unit test na niezmienniki (wymagane pola są, zakazanych
  konstrukcji nie ma). Bez tego prompt dryfuje przy każdej edycji.
- **Zmiana promptu = pokaż przed/po + oczekiwany wpływ.** Nie przepisujemy promptów po cichu
  przy okazji innej zmiany.
  
### Ewaluacja jakości

Jakość wyjścia LLM **mierz, nie oceniaj na oko.** Zbuduj golden set wejść, rubrykę
(fakty / kompletność / halucynacje / użyteczność) i zapisuj raport z datą i wersją promptu.

**Jak mierzyć:**
- **Powtórz każdą ewaluację ≥2 razy niezależnie** — `temperature=0` nie daje determinizmu
  (powtórzenia w jednej sesji próbkują ten sam bufor; ta sama komórka daje `3/3` i `0/3`).
  Rozbieżność między przebiegami to sygnał, nie szum.
- **Czytaj surowe odpowiedzi, nie tylko licznik** — walidator potwierdza dokładnie to, czego
  szuka (fałszywe „TAK", np. gdy heurystyka łapie wielką literę etykiety pola).
- **Włącz do próbki skrajności** — bardzo krótkie wejście, bardzo długie, z tabelą/strukturą;
  trzy typowe przypadki to nie próbka.
- **Nie rób autora tekstów sędzią** (LLM-as-judge) — to zalążek, nie harness; dąż do
  niezależnego sędziego i „złotych" odpowiedzi jako odniesienia.
- **Notuj wynik osobno per rozmiar modelu** — mniejszy wariant trzyma format luźniej niż
  większy przy tym samym prompcie.

**Jak projektować schemat odpowiedzi:**
- **Daj każdemu polu jawne wyjście** (`brak` / `nie dotyczy`) — pole obowiązkowe wymusza
  konfabulację, model wypełni je nawet gdy faktu nie ma.
- **Albo dodaj pole do schematu, albo każ parserowi ignorować nadmiarowe klucze** — model łamie
  zamkniętą listę, dokładając własne (cenne merytorycznie, groźne dla parsera).
- **Rozdziel pola o mieszanej semantyce** — jedno „Termin / data" zbiera raz datę pisma, raz
  termin merytoryczny; osobne pola zamiast liczenia na interpretację.
- **Daj danym liczbowym własne pola** (kwoty, sygnatury, identyfikatory) — inaczej giną.
- **Mierz osobno osie: do kiedy / co zrobić / do kogo / za ile** — sprawdzian formatu jest na
  nie ślepy, a to po nie produkt istnieje.

## Komentarze w kodzie

- Gęste, prowadzące wzrok.
- **„Dlaczego", nie „co"** — komentarz tłumaczy sedno: nieoczywiste zachowania API/SDK,
  obejścia, magiczne liczby, reguły biznesowe.
- **Separatory bloków** w ciele funkcji, nazwa opisuje blok np. `# --- build request ---`.
- **Każda gałąź osobno** — przy wielu `except`/`if` komentarz przy KAŻDEJ klauzuli.
- **Przykładowe wartości argumentów inline przy sygnaturze**. Dotyczy
  WSZYSTKICH metod, też prywatnych helperów:

  ```python
  def __init__(
      self,
      api_key:  str,        # e.g. "sk-proj-...HNkA"
      base_url: str,        # e.g. "https://api.openai.com/v1"
      model:    str,        # e.g. "gpt-4o-mini"
      timeout:  float = 60, # seconds
  ):
  ```

- **Wieloliniowo tylko z inline-komentarzem na każdej linii; inaczej jedna linia** (długie OK):

  ```python
  # obvious → one line, even if long
  client = OpenAILLMClient(api_key=key, base_url=url, model=model, timeout=60)
  
  # less obvious → split and comment each line
  except (
      APITimeoutError,     # network didn't respond within the timeout
      APIConnectionError,  # could not establish a connection
  ) as exc:
  ```

## Docstringi

- **Stały format, na KAŻDEJ metodzie** (też prywatnej i też implementacji metody
  interfejsu, nie tylko na abstrakcyjnej):

```
Description:
<what it does, briefly>

Example args:
    arg1=...
    arg2=...

Example result:
    <example return value>

Raises:                      # only when the method raises
    <Exception>: <when>
```

- Bez bloku `Args:` — opis argumentów idzie inline przy sygnaturze.
- Konstruktor: `Example result:` = opis skonfigurowanej instancji.
- **Docstring nietrywialnej klasy rozbudowany**, nie jednolinijkowy: „Do czego" (przeznaczenie
  + rola w architekturze) i „Flow" (przebieg krok po kroku, z odwołaniem do metod).

## Konfiguracja i deploy

**Konfiguracja (ENV):**
- Cała konfiguracja przez ENV (pydantic-settings) — żadnych sekretów/endpointów na sztywno.
- **Jeden `.env` w korzeniu** (nie per usługa; wartości rozdzielamy prefiksami `LLM_*`, `DB_*`).
  `.env` w `.gitignore`, **`.env.example` w repo = kontrakt** — każda zmienna z compose i
  `Settings` musi tam być. Bez `.env.prod`/`.env.dev` — różnice środowisk przez warstwy compose
  i ENV na maszynie docelowej.
- **ENV do kontenerów jawnie przez `environment:`**, nie `env_file:` — wtedy `docker compose
  config` pokazuje realny wynik interpolacji.
- **Prefiks nazywa właściciela zmiennej** — `LLM_*`, `DB_*` dzielą po komponencie, a `DOCKER_*`
  wydziela to, co **czyta sam compose i nigdy nie wchodzi do kontenera** (porty hosta, adres
  nasłuchu); inaczej takie wpisy wyglądają w `.env.example` na martwe.
- **Zgodności nazw pilnuje test, nie czujność przy review** — patrz „Testy" (plumbing configu).

**Pliki i warstwy compose:**
- **Wszystkie pliki compose w korzeniu** — tylko stamtąd Compose znajdzie `.env`, a ścieżki
  `build:` są jednoznaczne.
- `docker-compose.yml` = **baza (dev)**; warstwy `docker-compose.<cel>.yml`, gdzie `<cel>` =
  **to, co warstwa DODAJE**, nie środowisko (kaskada przez kropki). **Jeden wymiar na plik**
  („czy dokładamy komponent" ≠ „jak on liczy").
- **Dziedziczenie przez `include`**, nie multi-`-f`/`COMPOSE_FILE` — jeden `-f` podnosi łańcuch.
- **Warstwa dokłada tylko swoje** — nie majstruje przy cudzych usługach; zachowanie istniejących
  przełącza się jawnie w `.env`, nie magią w YAML. Warstwa produkcyjna rozłączna z opcjonalnymi.
- **Sprzęt (GPU) osobną warstwą** — aktywna rezerwacja twardo wywala start bez runtime GPU;
  baza ma być przenośna.

**Dev vs prod (kod):**
- **Baza montuje kod z hosta** (bind-mount) — zmiany `.py` żywe bez rebuildu.
- **Prod zdejmuje mount** — `docker-compose.prod.yml` kasuje wolumen przez `volumes: !reset []`
  (uruchamiamy kod z obrazu, nie z hosta).

**Pułapki:**
- **Pusty string zamiast braku** — `docker compose` dla niezdefiniowanego `${VAR:-}` wstawia
  **pusty string**. Bez walidatora „pusty/biały → `None`" w `Settings` dostajesz
  `Client(base_url="")` → błąd połączenia zamiast czytelnego błędu configu.
- **Powłoka przebija `.env`** — przy `${VAR:-default}` Compose stawia zmienną powłoki **wyżej**
  niż `.env`, cicho; jedno `set -a; . ./.env` zamraża stare wartości na resztę sesji. Stąd:
  **weryfikuj `docker compose config`, nie `.env`**.
- **Listy się SKLEJAJĄ, nie nadpisują** (`ports`, `volumes`) — warstwa nie „poprawi" wpisu
  z bazy, dostaniesz dwa. Zdjęcie: `!reset []` (Compose ≥ 2.24) — tak prod kasuje mount i tak
  zdejmujesz stary port. Zmiana adresu nasłuchu: ENV **w bazie** (`${BIND_ADDR:-0.0.0.0}`).

**Obrazy:**
- **Pinowane tagiem, bazowy digestem** (`python:3.12-slim@sha256:…`) — ruchomy tag daje przy
  rebuildzie inny obraz niż testowany.

## Logi i obserwowalność

- **Request-ID = korelacja logów, nie monitoring.** Nadawany/propagowany w middleware
  (nagłówek + logi), pozwala zszyć wpisy jednego żądania.
- **Przyczynę błędu logujemy w handlerach wyjątków, nie w middleware** — middleware widzi już
  gotową `Response`, a `detail` (jedyne „dlaczego") żyje tylko w wyjątku. Uwaga: `RequestValidationError`
  to **nie** `HTTPException` — potrzebuje osobnego handlera (najczęstsze 422).
- **Awaria zależności → 503 z generycznym komunikatem** (tekst wyjątku SDK potrafi zacytować
  prompt); szczegół zostaje w logu.
- **Błąd konfiguracji NIGDY nie zamienia się w status HTTP** — `…ConfigError` dziedziczy po
  błędzie warstwy, więc sam wpadnie w handler 503: handler musi go **wyrzucić z powrotem**.
- **Treści promptów/odpowiedzi/danych użytkownika: DEBUG, nigdy INFO.**

## Frontend

- Front to **statyka wpiekana w `api`** (`api/app/static/`), nie osobna usługa compose —
  dlatego nie występuje w warstwach compose (wyjątek od zasady 3: to nie komponent gadający REST-em).
- Pełny React (SPA) + Ant Design v6 (React ≥18; `antd` i `@ant-design/icons` w tej samej generacji major). Bez komponentów za paywallem.
- Pliki statyczne z React serwowane przez FastAPI — z tego samego origin. Dev: Vite z proxy `/api`.
- Wygląd przez tokeny antd w `ConfigProvider`. Bez Tailwinda.
- Nie rozbijaj małych komponentów na kilkanaście plików (np. nawigacja jako dane w configu, nie JSX).
- Wykresy: `@ant-design/charts`.

## Dokumentacja

- **CLAUDE.md** — „dlaczego": zasady, trwałe decyzje, pułapki, świadome pominięcia.
- **README** — „jak": uruchomienie i kontrakt dla użytkownika. Proponowany podział na sekcje:
  1. **Stack** — technologie i ich role.
  2. **Flow działania** — ogólny algorytm (wejście → etapy → wyjście).
  3. **Przykład end-to-end** — np. konkretny dokument wejściowy i wynikowe podsumowanie
     (ilustracja działania, nie sztywny format).
  4. **Szybkie uruchomienie** — np.:
     ```bash
     cp .env.example .env   # utwórz lokalną konfigurację z szablonu
     docker compose build   # zbuduj obrazy wszystkich usług
     docker compose up -d   # uruchom całą kompozycję
     ```
  5. **Konfiguracja** — wszystkie zmienne środowiskowe w tabeli (nazwa, domyślna, opis).
  6. **API** — tabela endpointów, a pod nią opis każdego (wywołanie, przykład wejścia, przykład wyjścia).
  7. **Integracje** — zawartość `integrations/` z przykładem użycia.
  8. **Uwagi techniczne.**
  9. **Testy** — jak uruchomić, markery.
  10. **Typowe procedury** — same kroki instruktażowe (rationale zostaje w CLAUDE.md).

## Testy

- **Dzielić wg odpowiedzialności na osobne pliki** — jeden plik = jedna jednostka/aspekt
  (`test_llm_fake.py` + `test_llm_factory.py` + `test_llm_openai.py` + `test_llm_openai_errors.py`),
  nie jeden zbiorczy.
- **Każdy test ma docstring** — jedna linia „scenariusz → oczekiwanie", spójnie we wszystkich
  testach pliku (nie część z docstringiem, część bez).
- **Bez obronnego boilerplate'u bez uzasadnienia.** Zadeklarowanych zależności (runtime i dev)
  **nie** guardujemy `pytest.importorskip` — brak zadeklarowanej zależności ma być głośnym
  `ImportError`, nie cichym skipem. `importorskip` zostaje tylko dla zależności faktycznie
  opcjonalnych.
- **Test integracyjny wymaga swojej usługi — cokolwiek nie tak (usługa nieosiągalna, brak klucza)
  = fail, nie skip.** Integracyjne i `llm_live` są za markerem, uruchamiane świadomie; skoro
  o nie prosisz, brak warunków do uruchomienia to błąd, nie powód do pominięcia. (Domyślny
  `pytest` = unity na atrapie, więc nic nie pada przez brak stacku.)
- **Markery:** `integration_<usługa>` + parasol `integration`; osobno `llm_live` (żywy, płatny LLM
  **poza** parasolem, żeby `-m integration` go nie łapał). Wszystkie rejestrowane w `pyproject.toml`.
- **Test plumbingu configu** — `.env.example` ↔ compose `environment:` ↔ `Settings` czytane jako
  dane (bez Dockera, więc unit). Trzy źródła = **trzy krawędzie po dwa kierunki, wszystkie sześć
  trzeba napisać**; ważniejszy jest kierunek „brak" (pole, którego usługa nie dostaje), bo wartość
  domyślna sprawia, że usługa cicho wstaje na wartości z kodu. Krawędź compose ↔ `Settings` licz
  **per usługa** — pośrednie „trafia do *jakiegoś* kontenera" przepuści odebranie zmiennej jednej
  z dwóch. Compose-only (`DOCKER_*`) wyklucz **predykatem, nie listą** — za cenę dwóch strażników
  odwrotnych (nie trafia do kontenera, nie deklaruje jej `Settings`). To test **nazw**, nie wartości.
- **`--import-mode=importlib`** w `addopts` — bez tego zbiorczy `pytest -m …` wywala „import file
  mismatch", gdy ten sam plik istnieje w `tests/unit/` i `tests/integration/`.
- **`-m 'not integration and not llm_live'` w `addopts`** — sama rejestracja markera niczego nie
  odsiewa; bez tego gołe `pytest` odpala też integracyjne. `-m` z linii poleceń nadpisuje.
- Unit testy **mockują klienta LLM**; realne API nigdy w domyślnym przebiegu.
- **Ile w pliku jest osi, tyle helperów — żadnego „helper i reszta ręcznie".** Sygnał: jeden test
  woła helper, a trzy następne sklejają to samo ręcznie — brakuje helpera, a nie tamte są
  wyjątkowe. Dopisz brakujący, a powtórzone testy zwiną się do jednej parametryzacji.
- **Atrapa z produkcji przed stubem pisanym w teście.** Jest `Fake…` (implementacja offline
  z fabryki)? Użyj jej — nawet gdy własny stub wygląda na mniejszy. **Rozstrzyga to, co
  sprawdzenie faktycznie czyta:** kontrola wymiaru czyta dwie właściwości, a `Fake…` obie ma,
  więc klasa z pełnym interfejsem byłaby czystą duplikacją. Stub dopiero wtedy, gdy atrapa nie
  umie odtworzyć badanego stanu. Zysk podwójny: mniej kodu i test pokazuje, **po co ta atrapa
  istnieje**.
- **Testy uruchamiaj JEDNYM poleceniem** — całość (`pytest -m ""`) albo podzbiór wskazany folderami
  i markerami (`pytest tests/integration/ tests/functional/ -m "integration or functional"`).
  Oszczędza kilkukrotne ładowanie ciężkich SDK i kolekcję testów.
  - **Przy debugowaniu czasu testów mierz sekwencyjnie i naprzemiennie A/B/A/B** — dwa przebiegi
    naraz mierzą obciążenie maszyny, nie kod. `--durations` pokaże, czy czas siedzi w testach,
    `--collect-only` — czy w imporcie.

**Atrapy transportu bierz z `tests/helpers_transport.py`** — zawsze, gdy testujesz klienta HTTP.
W pliku testu zostaje tylko budowa instancji klienta i atrapy jego własnych odpowiedzi.

| helper | co robi |
|---|---|
| `with_transport()` | podmienia transport klienta |
| `always()`         | jedna odpowiedź na wszystko |
| `routed()`         | odpowiedź per `(metoda, ścieżka)` |
| `capturing()`      | zapisuje wysłane żądania |
| `raising()`        | transport nie odpowiada wcale |

## Świadomie pominięte (NIE dodawać bez pytania)

Rejestr odrzuconych rozwiązań — narzędzi/podejść, które celowo pominęliśmy. Gdy podejmiemy
taką decyzję w trakcie pracy, **dopisz ją tu** (co + jednozdaniowe dlaczego). Jeśli zadanie
wydaje się wymagać czegoś z tej listy — zapytaj, zamiast wprowadzać.

_(pusta — uzupełniana w miarę decyzji)_

## TODO — przed wdrożeniem produkcyjnym

Luki „ostatniej mili", o których agent ma wiedzieć. Gdy natrafisz na taki brak (albo sam go
tworzysz świadomym skrótem), **dopisz go tu** zamiast zostawiać w milczeniu.

_(pusta — uzupełniana w miarę pracy)_

## Plan tworzenia aplikacji

Roadmapa budowy — etapy, ich kolejność i status. Trzyma kierunek prac i pokazuje, co już
gotowe, a co przed nami. Gdy skończymy etap albo zmienimy plan, **zaktualizuj tu status**
(np. `[x]` / `[~]` w trakcie / `[ ]`), a nowe etapy dopisuj z jednozdaniowym celem.

**Rytm pracy:** etap **przed wdrożeniem rozpisujemy tu na podkroki** — z kolejnością (co od czego
zależy) i sprawdzalnym kryterium ukończenia; rozpisany jest **tylko etap aktualny**, przyszłe
zostają jednolinijkowe. **Po zakończeniu zwijamy podkroki** do jednego punktu `[x]` scalonego
z opisem etapu — ale nie gubiąc wiedzy: trwałe ustalenia przenieś przed zwinięciem do właściwej
sekcji (reguła → sekcja tematyczna, odrzucona opcja → „Świadomie pominięte", pułapka → „Gotchas"
właściwej warstwy, skrót → „TODO").

**Etapy:**

_(pusta — uzupełniana w miarę prac)_
