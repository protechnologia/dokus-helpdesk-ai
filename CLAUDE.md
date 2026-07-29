# CLAUDE.md — dokus-helpdesk-ai

## Cel

Wsparcie LLM dla aplikacji helpdesk i pracujących z nią wdrożeniowców.

Na wejściu mamy **historyczną bazę zgłoszeń** — zrzut produkcyjnej bazy MariaDB helpdesku,
zawężony do **modułu Dokus** (patrz „Dane wejściowe"). Z niej budujemy **bazę wektorową (RAG)**,
a na jej podstawie aplikacja wspomaga wdrożeniowca — przede wszystkim **przygotowuje propozycję
odpowiedzi** na nowe zgłoszenie, opartą o rozwiązania podobnych spraw z przeszłości.

Kluczowa decyzja architektoniczna: **do RAG nie trafiają surowe zgłoszenia.** Każda konwersacja
przechodzi najpierw przez LLM, który zwraca **ustrukturyzowany JSON** (problem, objawy, system,
przyczyna, rozwiązanie, kategoria…). Dopiero ten JSON jest źródłem embeddingów i payloadu.

**Człowiek zawsze zatwierdza.** Produktem jest *propozycja* odpowiedzi dla wdrożeniowca, nigdy
automatyczna wysyłka do klienta.

## Zasady naczelne (NIE łamać bez wyraźnej decyzji)

1. **Konfiguracja wyłącznie przez ENV** (pydantic-settings) — żadnych sekretów ani
   endpointów na sztywno w kodzie.
2. **Komunikacja = REST (HTTP/JSON)** między komponentami.
3. **Modularność.** Każdy komponent = osobna usługa w `docker-compose`, którą da się podmienić
   lub zaktualizować **bez zmian w pozostałych** (i bez zmian w logice biznesowej).
4. **Abstrakcja dostawcy LLM** — logika nigdy nie rozmawia bezpośrednio z SDK dostawcy.
   To samo dotyczy **embeddera**: domena woła `EmbeddingClient`, nie `sentence-transformers`.
5. **Dev montuje kod z hosta** (zmiany żywe bez rebuildu); **prod kopiuje kod do obrazu** —
   uruchamiamy dokładnie tę wersję, którą zbudowaliśmy.
6. **Praca zawsze w izolowanym `venv`** — nigdy przeciw systemowemu Pythonowi. Przed każdą
   komendą Pythona (`pytest`/`ruff`/`pip`) `.venv` musi istnieć i być aktywny; jeśli go nie ma —
   najpierw utwórz i aktywuj.
7. **Sparsowany JSON zgłoszenia jest trwałym artefaktem na dysku, nie efektem ubocznym.**
   Embeddingi i kolekcje Qdranta są wymienne i odtwarzalne — przebieg LLM jest drogi
   i jednorazowy. Re-index **nigdy** nie wymaga ponownego wołania LLM.
8. **Qdrant jest indeksem, nie źródłem prawdy.** Musi dać się skasować i odbudować z katalogu
   JSON-ów jedną komendą.
9. **Nie zmyślamy treści merytorycznej.** Odpowiedź generowana jest wyłącznie z pól trafionych
   rekordów; brakujące dane to **placeholder** (`{IMIĘ}`, `{NR_URZĄDZENIA}`), nigdy wymyślona
   wartość. Brak trafień = brak propozycji z RAG, a nie propozycja „z głowy".

## Stack

- Python, FastAPI, Pydantic, pydantic-settings, Typer (CLI)
- **Baza wektorowa: Qdrant** — jedyna baza na tym etapie (brak SQL — patrz „Świadomie pominięte")
- **Embeddingi: lokalny model PL `OPI-PIB/PolDense-*`** (ModernBERT, rodzina 17M–1B; SOTA na
  PIRB). Cel: wariant **68M/150M** na RTX 4090 obok Bielika; mały wariant na dev/CPU.
  Licencja: **gemma** — zweryfikować przed komercyjnym wdrożeniem.
  Wymiar wektora = konfiguracja kolekcji Qdrant (zmiana modelu ⇒ nowa kolekcja, nie migracja).
- **LLM: docelowo Bielik 11B v3** (RunPod / lokalne GPU, endpoint zgodny z OpenAI); na dev
  dostawca chmurowy, domyślnie `FakeLLMClient` (offline).
- Deploy: Docker Compose

Usługi w compose: `api` (FastAPI + CLI), `embedder` (model PL za REST-em), `qdrant`.
LLM jest **zewnętrznym endpointem**, nie usługą w bazowym compose.

## Don't (szybka lista czerwonych flag)

- **Nie importuj SDK dostawcy poza plikiem klienta** (dotyczy też `sentence-transformers`
  poza usługą `embedder`)
- **Nie odpalaj testów na żywym LLM bez pytania**
- **Nie mieszaj trybów prefiksów PolDense w jednej przestrzeni wektorowej** (patrz „Embeddingi")
- **Nie wrzucaj pola `solution` do embeddingu** — rozwiązanie żyje w payloadzie, nie w wektorze
- **Nie indeksuj surowej treści maila** — indeksujemy wyłącznie sparsowane pola
- **Nie kasuj i nie nadpisuj plików w `data/parsed/`** — to niepowtarzalny wynik przebiegu LLM
- **Nie filtruj korpusu po `status = 'zamkniety'`** — Dokus kończy zgłoszenia na `rozwiazany`,
  `zamkniety` ma 5 sztuk na 1825 (patrz „Dane wejściowe")
- **Nie szukaj rozwiązań w tabeli `rozwiazanie`** — jest martwa; rozwiązanie to `komentarz`
  z `typ IN ('rozwiazanie','konczacy_zgloszenie')`
- **Nie wybieraj zakresu po `grupa_id` ani `projektid`** — tylko po `modulid = 116`

## Praca z agentem

- **Prośba o plan = zostajesz w planowaniu.** „Jaki masz plan?" / „co proponujesz?" → przedstaw
  plan i **czekaj**. Odpowiedzi na pytania doprecyzowujące to NIE jest zgoda na implementację.
  - Bez zgody wolno: rozpoznanie — czytanie plików, `docker compose config`, sondy w scratchpadzie.
  - Dopiero po zgodzie: edycja plików projektu.
- **Commity bez trailerów współautorstwa** (`Co-Authored-By` itp.).
- Język komunikacji: polski.

## Dane wejściowe (stan: znany — analiza 2026-07-29)

Dostaliśmy **zrzut MySQL/MariaDB bazy `helpdesk`** (`mysql_helpdesk_20260724-141140.sql`, 37 MB,
MariaDB 10.3, aplikacja na Doctrine/Symfony, 21 tabel). Nie jest to eksport plikowy ani skrzynka
mailowa — **źródłem jest relacyjna baza produkcyjna**, więc adapter w `ingest/` czyta SQL,
nie CSV.

**`data/raw/` jest zdejmowane ze zrzutu skryptem `scripts/export_raw_tickets.py`** — wiernie,
bez stripowania HTML-u i bez filtra jakości (filtr to decyzja etapu 4, zabetonowany w artefakcie
przestałby być widoczny). Eksport jest odtwarzalny i nie woła LLM-a, więc **nie podlega zasadzie
7** — w razie potrzeby wolno go powtórzyć albo zmienić jego kształt. Kolumny z hasłami nie są
czytane przez żadne zapytanie tego skryptu.

- **Import to cienka warstwa adapterów** — `api/app/ingest/`, jeden adapter na format źródłowy;
  reszta systemu widzi wyłącznie znormalizowany `RawTicket`.
- **Nie zaszywamy założeń o źródle w domenie.** Nazwy pól, kodowanie, sposób sklejania wątku
  w konwersację żyją w adapterze.
- **Dane zawierają PII** (nazwiska, adresy, telefony klientów). Traktujemy je jak wrażliwe:
  nigdy w logach na INFO, nigdy w commicie; `data/` w `.gitignore`, w repo tylko zanonimizowane
  przykłady.

### Zakres korpusu: wyłącznie moduł Dokus

**Interesuje nas jedna aplikacja — Dokus, czyli `zgloszenie.modulid = 116`.** Reszta bazy
(30 923 zgłoszenia dla ~124 modułów: Karty Kontowe, Podatki, KiP, FK…) jest poza zakresem.

**Zakres wybieramy po `modulid`, nigdy po grupie.** Grupa `Dokus` (`modul_zgloszenia.grupa_id`)
to linia aplikacji webowych, nie produkt — zawiera też eObywatel (106 zgłoszeń), CHEM-SPED,
Portal inwestora i GIS. Do tego `grupa_id` nie jest utrzymywany dla nowych modułów (część ma
`NULL`), a `projektid` jest niespójny z `id` i miejscami śmieciowy (`8888`, `88886`) — **żadne
z tych pól nie nadaje się na identyfikator.**

Liczby (stan zrzutu 2026-07-24): **1825 zgłoszeń** (2021-02 → 2026-07), 1740 zamkniętych,
**1496 użytecznych do RAG** (mają opis > 50 zn. i choć jeden komentarz > 50 zn.), z czego
**1327 ma komentarz jawnie oznaczony jako rozwiązanie**. Śr. 2,2 komentarza na zgłoszenie,
śr. długość opisu 598 zn. 138 zgłaszających z 34 instytucji. Przyrost ~500 użytecznych
rekordów rocznie i rosnący.

### Mapowanie tabel na `ParsedTicket`

| nasze pole | źródło w bazie |
|---|---|
| `ticket_id`  | `zgloszenie.id` |
| `date`       | `zgloszenie.created_at` |
| `problem`    | `zgloszenie.czego_dotyczy` |
| `symptoms`   | `zgloszenie.szczegolowy_opis` |
| `solution`   | `komentarz.tresc` przy `typ IN ('rozwiazanie','konczacy_zgloszenie')` |
| `category`   | `kategoria.nazwa` przez `zgloszenie.kategoriaid` (10 wartości w Dokusie) |
| `resolved`   | `zgloszenie.status` — **uwaga niżej** |
| `system`     | `modul_zgloszenia.nazwa` — **w tym zakresie stała, patrz niżej** |
| `confirmed`  | `zgloszenie.powod_zakonczenia` — **nie** `ocena_rozwiazania` (patrz niżej) |
| `cause`      | brak kolumny — do wyprowadzenia przez LLM z wątku |

### Pułapki tej bazy (sprawdzone na danych, nie zgadywane)

- **Statusem końcowym Dokusa jest `rozwiazany` (1735), nie `zamkniety` (5).** W całej bazie jest
  odwrotnie (26 933 `zamkniety`). Filtr `resolved` napisany pod „resztę bazy" **odrzuciłby cały
  korpus Dokusa** — to najłatwiejszy sposób na cichy pusty indeks.
- **Tabela `rozwiazanie` jest martwa** — 1 wiersz w całej bazie, `zgloszenie.rozwiazanieid`
  zerowe pokrycie. **Nie mylić jej z komentarzem `typ='rozwiazanie'`**, który jest realnym
  źródłem rozwiązań. Tak samo martwe: `przyczyna` i `ocena_rozwiazania` (0 wypełnionych w całej
  bazie).
- **`confirmed` bierzemy z `powod_zakonczenia`, nie z `ocena_rozwiazania`.** Pole ocen jest puste,
  ale powód zakończenia rozróżnia `akceptacja_propozycji_rozwiazania` (552 w Dokusie) od
  `zignorowanie_propozycji_rozwiazania` (413) — to jest ten sygnał, tylko pod inną nazwą.
  Pozostałe wartości (`komentarz_konczacy` 368, `NULL` 490) nie rozstrzygają — wtedy potwierdzenie
  trzeba wyczytać z treści wątku albo zostawić jako nieznane. **Nie mylić „brak potwierdzenia"
  z „klient zaprzeczył"** — zignorowanie propozycji to najczęściej cisza, nie sprzeciw.
- **`cause` nie ma kolumny, ale często jest w wątku** — konsultant opisuje przyczynę w treści
  rozwiązania („wyczerpanie połączeń do bazy przez konwersję LibreOffice", „certyfikat bez
  uprawnienia AddDocumentToSign"). To zadanie dla LLM-a przy parsowaniu, nie brak danych.
- **Część rozwiązań jest pusta merytorycznie** — „Już powinno działać", „Zamykam", „Proszę się
  przelogować". Formalnie to komentarz `typ='rozwiazanie'`, ale nie niesie wiedzy nadającej się
  do zaproponowania komuś innemu. **Filtr jakości musi to odsiewać**, inaczej RAG zwróci
  trafienie bez treści — gorsze niż brak trafienia, bo wygląda na odpowiedź.
- **Treści są w HTML** — tagi (`<p>`) i encje (`&#039;`, `&#34;`). Strip + unescape w adapterze,
  przed jakimkolwiek parsowaniem i embedowaniem.
- **Temat (`czego_dotyczy`) jest słabym sygnałem** — w całej bazie 24 749 unikalnych na 30 923,
  samo „błąd" 446×. Dedup po treści opisu, nie po temacie.
- **W całej bazie 89% zgłoszeń wyjechało do Mantisa** (`numer_mantis`), przez co komentarze
  z synchronizacji REST gubią FK autora i lądują z `typ='zwyczajny'` mimo że są rozwiązaniami.
  **Dokusa to nie dotyczy** (6 zgłoszeń z 1825 ma `numer_mantis`, 2 komentarze bez autora) —
  ale gdyby zakres kiedyś się rozszerzył, `typ` i autor przestają być wiarygodne.
- **Zrzut zawiera hasła** — `konsultant.haslo` i `uzytkownik.haslo` jako 32-znakowe hashe (MD5,
  bez bcrypt/argon) oraz `skrzynka_email.password`. **Do niczego ich nie potrzebujemy — adapter
  nie czyta tych kolumn**, nie trafiają nawet do kopii roboczej.
- **Błędne klucze obce w schemacie źródłowym:** `instytucje_to_moduly.modulid`
  i `instytucje_to_kategorie.kategoriaid` wskazują na `instytucja(id)` zamiast na
  `modul_zgloszenia(id)` / `kategoria(id)`. Nie joinować po nich.

## Domena: kontrakt sparsowanego zgłoszenia

Serce projektu. **Ten schemat jest kontraktem** — trzyma go model Pydantic w
`api/app/domain/ticket.py` i to on rozstrzyga, co jest poprawnym artefaktem.

Pola (robocze; doprecyzować na pierwszej realnej partii danych):

| pole | rola | embedowane |
|---|---|---|
| `ticket_id`   | identyfikator źródłowy                          | nie |
| `date`        | data zgłoszenia                                 | nie |
| `system`      | system/moduł, którego dotyczy                   | **tak** |
| `problem`     | zwięzły opis problemu (1–2 zdania)              | **tak** |
| `symptoms`    | objawy widziane przez użytkownika               | **tak** |
| `error_codes` | kody błędów, sygnatury, identyfikatory urządzeń | nie (→ sparse, etap 8) |
| `cause`       | ustalona przyczyna                              | nie |
| `solution`    | co konkretnie rozwiązało sprawę                 | **nie** |
| `category`    | kategoria ze słownika                           | nie |
| `resolved`    | czy sprawa zakończyła się rozwiązaniem          | nie |
| `confirmed`   | czy klient potwierdził skuteczność              | nie |

Zasady schematu (rozwinięcie „Jak projektować schemat odpowiedzi" niżej):

- **Każde pole ma jawne wyjście** (`brak` / `nie dotyczy`) — pole obowiązkowe wymusza
  konfabulację.
- **Embedujemy wyłącznie `system` + `problem` + `symptoms`.** `solution` i metadane idą do
  payloadu Qdranta. Powód: szukamy po *podobieństwie problemu*, nie rozwiązania — wektor
  zanieczyszczony rozwiązaniem miesza oba sygnały.
  - **Przy obecnym zakresie (`modulid = 116`) `system` jest stałą** — cały korpus to jeden
    moduł, więc pole nie filtruje, nie różnicuje, a do każdego wektora dokłada ten sam token.
    **Embedujemy `problem` + `symptoms`.** Regułę z `system` zostawiamy spisaną, bo wraca
    natychmiast, gdy zakres obejmie więcej niż jedną aplikację.
- **Filtr jakości przy indeksacji:** rekordy bez rozwiązania (`resolved = false`) nie trafiają
  do indeksu — nie ma z czego zaproponować odpowiedzi. `confirmed` podnosi wagę.
  - **`confirmed` i `cause` nie mają źródła w bazie** (`ocena_rozwiazania` i `przyczyna` są
    puste — patrz „Dane wejściowe"). Albo wypadają ze schematu, albo wyprowadza je LLM z wątku
    z jawnym wyjściem `brak`. **Decyzja w etapie 1.** Do tego czasu nie opieramy na `confirmed`
    żadnej wagi — nie ma czego ważyć.
- **Deduplikacja** powtarzalnych problemów — ten sam problem w 200 ticketach zalałby top-5.

## RAG — architektura

**Indeksacja** (offline, odpalana świadomie z CLI):

```
zgłoszenia źródłowe → [adapter] → RawTicket → [LLM parser] → ParsedTicket (JSON na dysku)
                                                                    │
                              data/parsed/*.json ──────────────────┘
                                     │
                                     ├─ filtr (resolved) + dedup
                                     ├─ [embedder] system+problem+symptoms → wektory
                                     └─ upsert do Qdranta (wektory + payload)
```

**Zapytanie** (runtime):

```
nowe zgłoszenie (surowy tekst)
      │
      ├─ [LLM parser] → ParsedTicket (ten sam schemat i ten sam prompt co przy indeksacji)
      ├─ [embedder] system+problem+symptoms → wektor zapytania
      ├─ top-K z Qdranta → próg score → dedupe
      └─ 1–3 rekordy (payload, nie surowe maile) → [LLM + szablon] → propozycja
```

**Nowe zgłoszenie parsujemy PRZED wyszukaniem.** Powody: surowy mail (powitanie, stopka,
historia wątku) zaszumia wektor zapytania, a parser sprowadza obie strony porównania do tego
samego kształtu tekstu. Koszt to jedno dodatkowe wywołanie LLM na zapytanie — w przepływie,
który i tak woła LLM do generacji odpowiedzi.

Konsekwencja dla embeddingów: skoro **obie strony to ten sam rodzaj tekstu**, porównanie jest
symetryczne i tryb `sts` staje się równoprawnym kandydatem wobec `query→passage` — patrz niżej.

**Poza tym etapy są rozdzielone.** Masowe parsowanie korpusu (drogie, jednorazowe) nie jest
wołane ani przy indeksacji, ani przy zapytaniu — przy zapytaniu parsujemy wyłącznie ten jeden
przychodzący ticket.

### Embeddingi i prefiksy PolDense (najłatwiejsza rzecz do zepsucia)

PolDense rozróżnia tryby **prefiksem doklejanym do tekstu wejściowego**. Ten sam tekst z innym
prefiksem daje **inny wektor** — trybów **nie wolno mieszać w jednej przestrzeni wektorowej**.

| tryb | prefiks | zastosowanie |
|---|---|---|
| query   | `[query]: ` | nowe zgłoszenie w runtime (pytanie do bazy) |
| passage | *(brak)*    | podsumowanie problemu przy indeksacji (dokument-cel) |
| sts     | `[sts]: `   | porównania zgłoszenie↔zgłoszenie: dedup, „podobne przypadki" |

Konsekwencje:

- Opakowujemy to w **`embed_query()` / `embed_passage()` / `embed_sts()`** — nikt nie skleja
  prefiksu ręcznie w kodzie domenowym.
- **Nie wolno mieszać stron:** `[query]:` szuka wyłącznie po wektorach passage, `[sts]:`
  wyłącznie po wektorach sts.
- **Dwa named vectors na rekord** (`problem` = passage, `sts` = sts). Wektor `sts` jest
  bezdyskusyjny — dedup i „podobne przypadki" to porównanie zgłoszenie↔zgłoszenie, symetryczne
  z definicji.
- **Którym trybem szukać — pytanie otwarte, rozstrzygane pomiarem (etap 3), nie z góry.**
  Skoro zapytanie parsujemy przed wyszukaniem, obie strony są tym samym rodzajem tekstu, więc
  `sts→sts` jest naturalnym kandydatem; z drugiej strony tryb retrieval jest trenowany na luźnym
  dopasowaniu tematycznym (inne słowa, ta sama intencja), a STS bliżej parafrazy — przy
  zgłoszeniach opisywanych przez klientów skrajnie różnie to realna różnica.
- **Drugi wektor to zabezpieczenie do czasu pomiaru, nie docelowa architektura.** Kosztuje jedno
  dodatkowe wywołanie embeddera przy indeksacji i podwójną pamięć na wektory (przy 68M/150M
  i skali helpdesku — pomijalne). **Gdy pomiar wskaże zwycięzcę, przegrany wektor znika.**
- Zmiana modelu embeddingowego albo trybu ⇒ **nowa kolekcja i pełny re-index** (tani — JSON-y
  leżą na dysku).

### Wybór modelu embeddingowego i trybu — mierzyć, nie zgadywać

**Przed pełną indeksacją: mini-ewaluacja `recall@5`** na własnych parach testowych
(zgłoszenie → oczekiwany historyczny ticket). Dwie osie, mierzone niezależnie:

1. **Model:** PolDense vs `mmlw-roberta-large` vs `BGE-M3`.
2. **Tryb:** `query→passage` vs `sts→sts`, każdy z zapytaniem **surowym** i **sparsowanym** —
   bo dopiero to pokazuje, ile daje sam parser, a ile wybór trybu.

Wynik z datą, wariantem modelu i trybem zapisujemy w repo — to decyzja, do której będziemy
wracać, i to ona kasuje jeden z dwóch named vectors.

### Generacja propozycji odpowiedzi

- **Trafienia dają treść merytoryczną, prompt zadaje styl.** Do promptu idą pola z payloadu
  (`problem`, `cause`, `solution` + metadane: score, data, `ticket_id`) — **nie** surowe maile.
- **Top-5 → próg score → dedupe → 1–3 rekordy** do promptu. Więcej rozmywa odpowiedź.
- **Routing 3-ścieżkowy** (decyzja po score i zgodności trafień):
  1. **wysoki score + zgodne rozwiązania** → pełny szablon odpowiedzi,
  2. **średni score / sprzeczne rozwiązania** → szablon **diagnostyczny** (pytania do klienta),
  3. **niski score** → brak generacji z RAG + flaga **„nowy typ problemu"**.
- **Placeholdery zamiast danych** (`{IMIĘ}`, `{NR_URZĄDZENIA}`), nawiasy kwadratowe na
  instrukcje dla człowieka (`[dla serwisanta: sprawdź wersję firmware]`).
- Propozycja **zawsze** wraca z listą źródeł (ID ticketów + score) — wdrożeniowiec musi móc
  zweryfikować, skąd to się wzięło.

## Commands

**Uruchomienie**
- Dev (kod montowany z hosta): `docker compose -f docker-compose.yml up -d`
- Prod (bez montowania): `docker compose -f docker-compose.prod.yml up -d`
- Z GPU dla embeddera: warstwa `docker-compose.gpu.yml`
- Po zmianie zależności lub `Dockerfile` (albo kodu na prodzie): `docker compose up -d --build <usługa>`
- Weryfikacja realnej konfiguracji: `docker compose config` (nie zawartość `.env`)

**Przygotowanie danych (skrypty repo)**
- Eksport zgłoszeń ze zrzutu do `data/raw/`: `python scripts/export_raw_tickets.py export --module-id 116`
  (wymaga kontenera z zaimportowanym zrzutem; kontrola liczb wobec bazy na końcu przebiegu)

**Pipeline danych (CLI `dokus`)**
- Walidacja artefaktów: `dokus tickets validate data/parsed/`
- Indeksacja do Qdranta: `dokus index build --collection <nazwa>`
- Pełna odbudowa indeksu: `dokus index rebuild` (kasuje kolekcję, wstaje z `data/parsed/`)
- Zapytanie z konsoli: `dokus search "treść zgłoszenia"`
- Ewaluacja embeddera: `dokus eval recall --model <nazwa>`

**Testy i jakość**
- Lint: `ruff check .`
- Jednostkowe (LLM = atrapa): `pytest`
- Integracyjne: `pytest -m integration_<usługa>` (albo parasol `pytest -m integration`)
- Na żywym LLM: `pytest -m llm_live` — **kosztuje / bije po sieci, pytaj przed**

**CLI / pakiet**
- `pip install -e .` — tylko po zmianie `pyproject.toml`, po zmianie kodu nigdy

## Podział na foldery i pliki

```
dokus-helpdesk-ai/
├── docker-compose.yml            # baza — api + embedder + qdrant
├── docker-compose.gpu.yml        # warstwa: rezerwacja GPU dla embeddera
├── docker-compose.prod.yml       # warstwa: kod z obrazu (volumes: !reset [])
├── .env                          # wartości lokalne — NIE w repo
├── .env.example                  # kontrakt konfiguracji — W repo
├── pyproject.toml                # pytest/lint + pakietowanie (entry-point `dokus`)
├── requirements-dev.txt          # zależności testów/lintera (poza obrazem)
├── CLAUDE.md / README.md
├── scripts/                      # narzędzia repo niezwiązane z usługą (patrz „Warstwa CLI")
├── data/                         # artefakty — NIE w repo (PII)
│   ├── raw/                      # zgłoszenia źródłowe jak przyszły
│   └── parsed/                   # sparsowane JSON-y (trwały artefakt, zasada 7)
├── api/                          # folder = usługa z compose, nazwany tak samo
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── requirements.txt          # zależności RUNTIME tej usługi (do obrazu)
│   ├── scripts/                  # skrypty deweloperskie (python api/scripts/…)
│   └── app/                      # kod aplikacji
│       ├── cli/                  # CLI produkcyjne (Typer) — cienkie adaptery nad domeną
│       ├── main.py               # montaż aplikacji, middleware, handlery wyjątków
│       ├── config.py             # Settings (pydantic-settings)
│       ├── models.py             # modele API (odrębne od domenowych)
│       ├── prompts/              # szablony promptów (parser zgłoszeń, generator odpowiedzi)
│       ├── routers/              # jeden plik na zasób/endpoint, cienkie
│       ├── domain/               # ParsedTicket, reguły filtrowania i routingu
│       ├── ingest/               # adaptery formatów źródłowych → RawTicket
│       ├── llm/                  # LLMClient + fabryka + FakeLLMClient
│       ├── embedding/            # EmbeddingClient (HTTP do `embedder`) + prefiksy
│       └── retrieval/            # klient Qdranta: indeksacja, wyszukiwanie
├── embedder/                     # kolejna usługa: model PL za REST-em
│   ├── Dockerfile
│   ├── requirements.txt
│   └── embedder_app/             # pakiet nazwany rozłącznie z `app` z `api/` (patrz „Testy")
│       ├── main.py               # montaż aplikacji
│       ├── config.py             # Settings tej usługi (własne, kodu nie dzielimy)
│       ├── models.py             # kontrakt HTTP: EmbedRequest/EmbedResponse, tryby prefiksów
│       ├── encoding/             # Encoder + fabryka + FakeEncoder — tu wchodzi PolDense
│       └── routers/              # /health, /embed
├── tests/
│   ├── unit/
│   └── integration/
├── integrations/<język>/         # klienci dla konsumentów API
└── samples/                      # zanonimizowane dane do testów i ewaluacji
```

- **Folder = usługa z compose**; wszystko do zbudowania obrazu leży w nim, nie w korzeniu.
  Korzeń należy do infrastruktury: compose, `.env*`, dokumentacja, config testów.
- **Testy w korzeniu, nie w folderze usługi** — nie trafiają do obrazu, a integracyjne sięgają
  kilku usług. Ten sam plik może być w `unit/` i `integration/` (stąd `--import-mode=importlib`).
- **Dwa pliki zależności:** `<usługa>/requirements.txt` = runtime, do obrazu;
  `requirements-dev.txt` w korzeniu = testy/lint, nigdy w obrazie.

## Warstwy kodu

- **Transport vs domena.** Transport = rozmowa z usługą zewnętrzną (LLM, embedder, Qdrant); domena =
  logika, nieświadoma tego, co pod spodem. Domena dostaje klienta transportowego przez
  konstruktor, nigdy nie sięga po SDK.
- **Klient per usługa.** Jedna implementacja → klient tworzony wprost. Klient
  wymienny → z fabryki po configu (np. LLM: chmura na dev, Bielik na prod).
- **„Klient" znaczy przekroczenie granicy procesu.** `EmbeddingClient` w `api` mówi HTTP-em do
  usługi `embedder`; to, co **wewnątrz** tej usługi liczy wektory, klientem nie jest i tak się
  nie nazywa (`Encoder`, `FakeEncoder`) — inaczej ta sama nazwa znaczyłaby dwie różne rzeczy
  w dwóch usługach. Wzorzec za to jest ten sam po obu stronach: interfejs + implementacja
  offline (`Fake…`) + fabryka po ENV z fail-fast.
- **Funkcja czy klasa — rozstrzyga stan, nie symetria.** Implementacja z cyklem życia (wagi
  modelu, sesja HTTP) to obiekt budowany raz; obliczenie bezstanowe zostaje funkcją modułową
  wołaną przez tę implementację (`deterministic_vector` wewnątrz `FakeEncoder`).
- **Handlery cienkie** — żądanie → serwis → odpowiedź; zero logiki i LLM w handlerze.
- **Osobne modele domenowe i API.** Encje/obiekty domeny nie wychodzą wprost przez HTTP —
  przepisujemy jawnie. Chroni kontrakt i blokuje wyciek pól wewnętrznych (ID, scoring).
  
## Styl kodu

- Język kodu, identyfikatorów, docstringów i komentarzy: **angielski**.
- **Brak autoformattera — świadomie.** `ruff format`/`black` zjadłyby pionowe wyrównanie `=`
  (niżej). Używamy `ruff check` (linter), nie formattera.
- **Importy zawsze na górze modułu.** Lazy import tylko przy realnym problemie (cykl albo
  faktycznie opcjonalna zależność) — nie „na wszelki wypadek". Konsekwencja przyjęta świadomie:
  import modułu pociąga jego zależności; przy zależnościach twardych to OK.
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

Trzy kategorie, których nie mieszamy:
1. **Repo-level** — `scripts/*.py`, narzędzia niezwiązane z żadną usługą (przygotowanie danych,
   jednorazowe migracje artefaktów). Uruchamiane `python scripts/nazwa.py`.
2. **Deweloperskie usługi** — `<usługa>/scripts/*.py`, sięgają do kodu, configu albo endpointów
   tej usługi. Uruchamiane `python api/scripts/nazwa.py`.
3. **Produkcyjne** — `api/app/cli/cli.py`, jeden wpis w `[project.scripts]` na całe drzewo subkomend.

**Kryterium podziału 1 vs 2: czy skrypt dotyka konkretnej usługi.** Eksport zrzutu bazy do
`data/raw/` nie importuje `api.app` i nie odpytuje żadnego endpointu — jest repo-level. Sonda po
`Settings` albo po `/embed` należy do usługi. Ta sama logika co przy nazwach testów: prefiks
usługi dostaje to, co jej dotyczy, a rzeczy ponadusługowe zostają bez niego.

**Skrypty z `scripts/` nie mają własnego `requirements.txt`** — nie trafiają do żadnego obrazu.
Zależności biorą z `.venv`: `requirements-dev.txt` albo edytowalnej instalacji `api` (stamtąd
Typer). Poza tym trzymamy je na bibliotece standardowej.

Wspólne:
- Framework: Typer.
- Wpis w `[project.scripts]` = osobna komenda (`dokus`); `@cli.command()` = subkomenda (`dokus index build`).
- `pip install -e .` tylko po zmianie pyproject.toml, po zmianie kodu nigdy.
- CLI to cienkie adaptery nad serwisami domenowymi (jak handlery HTTP) — zero logiki w komendzie.
- **Komendy niszczące (`index rebuild`) pytają o potwierdzenie** albo wymagają `--yes`.

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
- **Domyślnie `FakeLLMClient`** (offline) — `up` i `pytest` nic nie wysyłają i nic nie kosztują;
  realny dostawca włączany jawnie w ENV.
- **Endpoint zgodny z API OpenAI** (Ollama, vLLM, proxy) → model lokalny tym samym klientem,
  wystarczy `LLM_BASE_URL` + `LLM_MODEL`. **Tą samą drogą wchodzi Bielik na RunPodzie.**
  Inny kształt API (Azure) → osobny klient, nie `if` w istniejącym.
- **Wywołania async z jawnym timeoutem.**
- **`temperature` z ENV** (domyślnie `0`) — parsowanie zgłoszeń zawsze na `0`.
- **Walidacja wyjścia:** parsuj do modelu Pydantic; błąd → **jeden** retry z feedbackiem, potem
  porażka (nie pętla).
- **Retry sieciowy tylko z backoffem i capem prób.**
- **Loguj każde wywołanie:** model, tokeny in/out, latencja, koszt (log strukturalny). Treści
  promptu/odpowiedzi **nigdy na INFO** (dane użytkownika) — tylko DEBUG.

### Prompty

- **Prompt = logika, nie konfiguracja** — szablony w kodzie (`api/app/prompts/`, jeden plik na
  prompt), **nigdy w ENV**.
- **Prompt parsujący zgłoszenie mieszka w repo od pierwszego dnia** — nawet gdy pierwszą partię
  parsujemy ręcznie w czacie Claude. Ręczny przebieg ma używać **dokładnie tego** pliku; inaczej
  bootstrapowe JSON-y rozjadą się ze schematem, który potem wymusi aplikacja.
- **Każdy prompt ma test-strażnik** — unit test na niezmienniki (wymagane pola są, zakazanych
  konstrukcji nie ma). Bez tego prompt dryfuje przy każdej edycji.
- **Zmiana promptu = pokaż przed/po + oczekiwany wpływ.** Nie przepisujemy promptów po cichu
  przy okazji innej zmiany.
  
### Ewaluacja jakości

Jakość wyjścia LLM **mierz, nie oceniaj na oko.** Zbuduj golden set wejść, rubrykę
(fakty / kompletność / halucynacje / użyteczność) i zapisuj raport z datą i wersją promptu.

W tym projekcie mierzymy **dwie osie osobno**: jakość **retrievalu** (`recall@5` — czy właściwy
ticket w ogóle wpadł do top-5) i jakość **generacji** (czy propozycja odpowiedzi jest użyteczna).
Zła odpowiedź przy dobrym trafieniu to inny problem niż dobra odpowiedź z pustego indeksu.

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
  większy przy tym samym prompcie. Dotyczy zarówno Bielika, jak i wariantów PolDense.

**Jak projektować schemat odpowiedzi:**
- **Daj każdemu polu jawne wyjście** (`brak` / `nie dotyczy`) — pole obowiązkowe wymusza
  konfabulację, model wypełni je nawet gdy faktu nie ma.
- **Albo dodaj pole do schematu, albo każ parserowi ignorować nadmiarowe klucze** — model łamie
  zamkniętą listę, dokładając własne (cenne merytorycznie, groźne dla parsera).
- **Rozdziel pola o mieszanej semantyce** — jedno „Termin / data" zbiera raz datę pisma, raz
  termin merytoryczny; osobne pola zamiast liczenia na interpretację.
- **Daj danym liczbowym własne pola** (kwoty, sygnatury, identyfikatory) — inaczej giną.
  Tu: kody błędów i numery urządzeń mają własne pole, bo po nich będzie szło wyszukiwanie.
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
- **Jeden `.env` w korzeniu** (nie per usługa; wartości rozdzielamy prefiksami `LLM_*`,
  `EMBEDDING_*`, `QDRANT_*`, `RAG_*`). `.env` w `.gitignore`, **`.env.example` w repo =
  kontrakt** — każda zmienna z compose i `Settings` musi tam być. Bez `.env.prod`/`.env.dev` —
  różnice środowisk przez warstwy compose i ENV na maszynie docelowej.
- **Progi i parametry retrievalu (`RAG_TOP_K`, `RAG_SCORE_MIN`…) idą do ENV** — to strojenie,
  nie logika. Ale **reguły routingu 3-ścieżkowego zostają w kodzie**: decyzja „pełny szablon czy
  diagnostyczny" to logika biznesowa, nie konfiguracja.
- **ENV do kontenerów jawnie przez `environment:`**, nie `env_file:` — wtedy `docker compose
  config` pokazuje realny wynik interpolacji.
- **Test plumbingu configu** — parsuje `.env.example` ↔ compose `environment` ↔ `Settings` jako
  dane (bez Dockera) i pilnuje zgodności nazw w obie strony. Granica: sprawdza **przepływ nazw**,
  nie zachowanie — zły typ czy jednostka przejdzie.

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
  baza ma być przenośna. Tu dotyczy usługi `embedder` (PolDense na RTX 4090).

**Dev vs prod (kod):**
- **Baza montuje kod z hosta** (bind-mount) — zmiany `.py` żywe bez rebuildu.
- **Prod zdejmuje mount** — `docker-compose.prod.yml` kasuje wolumen przez `volumes: !reset []`
  (uruchamiamy kod z obrazu, nie z hosta).

**Trwałość danych:**
- **Wolumen Qdranta to wygoda, nie kopia zapasowa** — źródłem prawdy jest `data/parsed/`
  (zasada 8). Backup dotyczy katalogu JSON-ów, nie kolekcji.

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
  rebuildzie inny obraz niż testowany. Dotyczy też obrazu Qdranta.

## Logi i obserwowalność

- **Request-ID = korelacja logów, nie monitoring.** Nadawany/propagowany w middleware
  (nagłówek + logi), pozwala zszyć wpisy jednego żądania.
- **Przyczynę błędu logujemy w handlerach wyjątków, nie w middleware** — middleware widzi już
  gotową `Response`, a `detail` (jedyne „dlaczego") żyje tylko w wyjątku. Uwaga: `RequestValidationError`
  to **nie** `HTTPException` — potrzebuje osobnego handlera (najczęstsze 422).
- **Awaria zależności ma własny handler i status „spróbuj później".** Wyjątek warstwy
  transportowej (dziś `EncoderError` w embedderze) łapiemy osobno i zwracamy **503** we wspólnym
  kształcie `ErrorResponse` — surowy 500 nie odróżnia „model chwilowo padł" od „zapytanie jest
  błędne", a to decyduje, czy przebieg indeksacji ma ponowić, czy porzucić zgłoszenie.
  **Treść wyjątku zostaje w logu, nie w odpowiedzi** — komunikat biblioteki modelu potrafi
  zacytować wejście, czyli dane klienta.
- **Błąd konfiguracji NIGDY nie zamienia się w status HTTP.** `LLMConfigError`/`EncoderConfigError`
  dziedziczą po błędzie swojej warstwy, więc wpadłyby w handler 503 — handler **wyrzuca je z
  powrotem**. Powód: 503 znaczy „spróbuj za chwilę", a przy złym `LLM_PROVIDER` czekanie nic nie
  da; zielony kontener oddający uprzejme 503 na każde żądanie jest gorszy niż głośna śmierć.
- **Każda usługa ma swoje handlery i swój Request-ID** — kodu nie dzielimy, więc to świadome
  powielenie; id **przyjęte od wołającego wygrywa**, żeby jeden identyfikator spinał `api`
  i embedder w jednym przebiegu indeksacji.
- **Treści promptów/odpowiedzi/danych użytkownika: DEBUG, nigdy INFO.** Treść zgłoszenia
  i trafienia z RAG to dane klienta — na INFO wyłącznie identyfikatory i score.

## Frontend (jeszcze nie budujemy)

Na tym etapie projekt to **API + CLI**; UI dochodzi później (etap 8 roadmapy). Gdy dojdzie,
obowiązują poniższe zasady — spisane teraz, żeby decyzja nie zapadła przypadkiem:

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
  3. **Przykład end-to-end** — konkretne zgłoszenie wejściowe, trafienia z RAG i wynikowa
     propozycja odpowiedzi (ilustracja działania, nie sztywny format).
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
  (`test_api_llm_fake.py` + `test_api_llm_factory.py` + `test_api_llm_openai.py` +
  `test_api_llm_openai_errors.py`), nie jeden zbiorczy.
- **Nazwa pliku zaczyna się od usługi, której test dotyczy** (`test_api_*`, `test_embedder_*`) —
  przy kilku usługach sama nazwa mówi, co się psuje. **Bez prefiksu zostają testy
  ponadusługowe** (`test_config_plumbing.py` sprawdza `.env.example` wobec `Settings` wszystkich
  usług) — doklejenie im nazwy jednej usługi kłamałoby o zakresie.
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
- **Markery:** `integration_qdrant`, `integration_embedder` + parasol `integration`; osobno
  `llm_live` (żywy, płatny LLM **poza** parasolem, żeby `-m integration` go nie łapał).
  Wszystkie rejestrowane w `pyproject.toml`.
- **Domyślny przebieg wyklucza markery jawnie** — `-m 'not integration and not llm_live'`
  w `addopts`. Sama rejestracja markera niczego nie odsiewa: bez tego gołe `pytest` odpala też
  integracyjne i jest zielone tylko wtedy, gdy akurat chodzi stack. `-m` z linii poleceń
  **nadpisuje** tę wartość, więc `pytest -m integration_embedder` dalej wybiera dokładnie to,
  o co prosi.
- **Pakiety usług mają rozłączne nazwy** (`api/app/`, `embedder/embedder_app/`) — wszystkie
  drzewa są importowalne w JEDNYM procesie pytest, a dwa pakiety najwyższego poziomu o tej samej
  nazwie zasłaniałyby się nawzajem (`sys.modules` zapamiętuje pierwszy import, więc kolejność
  decydowałaby, którą usługę faktycznie testujesz). W kontenerze nazwa nie ma znaczenia — ta
  decyzja istnieje wyłącznie po to, żeby o testach jednostkowych nie rozstrzygała nazwa katalogu.
- **Usługa nieopakowana jako pakiet dochodzi przez `pythonpath` w `pyproject.toml`** — tylko
  `api` jest instalowane (`pip install -e .`), reszta jedzie wyłącznie w swoim obrazie.
- **Podział testów usługi: kontrakt w procesie, wdrożenie po HTTP.** Linia podziału biegnie po
  tym, CO test może udowodnić — nie po tym, której usługi dotyczy (obie mają być traktowane
  tak samo):
  - **jednostkowo, offline:** logika czysta (np. `deterministic_vector`) oraz kontrakt aplikacji
    na `TestClient` — kody odpowiedzi, walidacja żądania, kształt payloadu;
  - **integracyjnie, za markerem:** to, czego prawdziwość mieszka **poza naszym kodem** —
    zachowanie realnej zależności (czy Qdrant naprawdę tak filtruje i sortuje, czy model
    naprawdę daje inne wektory dla `[query]:` i `[sts]:`) oraz wdrożenie (obraz się zbudował,
    `CMD` wskazuje właściwy moduł, port opublikowany, ENV doszło). Gdy pod spodem nie ma
    zewnętrznej prawdy — jak przy backendzie `fake` — zostaje z tego **cienki smoke**
    (`/health` + jedno realne wywołanie); powtarzanie w nim walidacji tylko wydłuża przebieg
    wymagający stacku.
- **Deterministyczna atrapa ma test „złotej wartości"** — zapisany wektor dla znanego tekstu.
  Bez niego refaktor cicho zmienia odwzorowanie tekst→wektor i zaindeksowane wektory przestają
  pasować do świeżo policzonych; wartość aktualizujemy **razem ze świadomą zmianą** algorytmu.
- **Testy async przez `pytest-asyncio` w trybie `asyncio_mode = "auto"`** — klienci transportowi
  (LLM, embedder, Qdrant) są async, więc ich testy są korutynami; tryb `auto` uruchamia każdy
  `async def test_*` bez dekoratora na każdym teście.
- **`--import-mode=importlib`** w `addopts` — bez tego zbiorczy `pytest -m …` wywala „import file
  mismatch", gdy ten sam plik istnieje w `tests/unit/` i `tests/integration/`.
- Unit testy **mockują klienta LLM i embedder**; realne API nigdy w domyślnym przebiegu.
- **Retrieval testujemy na deterministycznej atrapie embeddera** (stały wektor per tekst) —
  test progów, dedupe i routingu nie ma prawa zależeć od modelu.
- **Klientem HTTP dla `TestClient` jest `httpx2`, nie `httpx`** — Starlette ≥ 1.3 uznaje `httpx`
  za przestarzały i przy każdym przebiegu sypie `StarletteDeprecationWarning`. Oba pakiety
  zainstalowane obok siebie nie kolidują, ale ostrzeżenie znika dopiero po usunięciu `httpx`.
- **Handlery wyjątków testujemy na nagiej aplikacji** (`register_exception_handlers` + trasy
  prowokujące błąd), nie na prawdziwej — inaczej test zależy od tego, jakie endpointy
  przypadkiem istnieją. Do tego `TestClient(app, raise_server_exceptions=False)`, bo domyślnie
  wyjątek leci do testu, zamiast trafić do handlera.

## Świadomie pominięte (NIE dodawać bez pytania)

Rejestr odrzuconych rozwiązań — narzędzi/podejść, które celowo pominęliśmy. Gdy podejmiemy
taką decyzję w trakcie pracy, **dopisz ją tu** (co + jednozdaniowe dlaczego). Jeśli zadanie
wydaje się wymagać czegoś z tej listy — zapytaj, zamiast wprowadzać.

- **Relacyjna baza (MariaDB)** — źródłem prawdy są JSON-y na dysku, indeksem Qdrant; SQL wejdzie
  dopiero gdy pojawi się potrzeba audytu/feedbacku/statystyk (patrz TODO).
- **Frontend (React SPA)** — na starcie API + CLI; UI to etap 8.
- **Masowe parsowanie korpusu w aplikacji** — pierwszą partię parsujemy ręcznie w czacie Claude
  wg promptu z repo; wsadowy import to etap 7. Nie dotyczy parsera pojedynczego zgłoszenia —
  ten wchodzi już w etapie 5, bo zapytanie parsujemy przed wyszukaniem.
- **Framework RAG (LangChain / LlamaIndex)** — piszemy wprost na kliencie Qdranta; warstwa
  pośrednia ukryłaby dokładnie te rzeczy, które tu kontrolujemy ręcznie (prefiksy, named vectors,
  progi, routing).
- **Hybrid search (dense + BM25/sparse)** — świadomie na później (etap 8), mimo że kody błędów
  i nazwy urządzeń go potrzebują; najpierw czysty dense z pomiarem.
- **Reranker (cross-encoder na top-10)** — dopiero gdy pomiar pokaże, że top-5 gubi trafienia.
- **Synthetic queries jako dodatkowy named vector** — rozważane, nieprzyjęte.
- **Automatyczna wysyłka odpowiedzi do klienta** — produktem jest propozycja dla wdrożeniowca.
- **Zgłoszenia spoza modułu Dokus** — w bazie jest ich 29 tys. z ~124 modułów, ale zakres
  projektu to jedna aplikacja; ich włączenie to nowa decyzja, nie rozszerzenie filtra
  (wraca wtedy `system` do embeddingu i przestaje działać założenie o wiarygodnym `typ`
  komentarza — patrz „Dane wejściowe").
- **Załączniki zgłoszeń** — 16 634 plików w całej bazie, ale `zalacznik` trzyma tylko ścieżki,
  samych plików w zrzucie nie ma; treść zgłoszenia i wątku wystarcza.

## TODO — przed wdrożeniem produkcyjnym

Luki „ostatniej mili", o których agent ma wiedzieć. Gdy natrafisz na taki brak (albo sam go
tworzysz świadomym skrótem), **dopisz go tu** zamiast zostawiać w milczeniu.

- **PII w danych historycznych** — ustalić politykę: anonimizacja przy parsowaniu czy tylko
  kontrola dostępu. Decyzja wpływa na schemat i na to, co wolno trzymać w payloadzie Qdranta.
  Kontekst z realnych danych: PII jest gęste (`osoba_kontakt`/`email_kontakt`/`telefon_kontakt`
  wypełnione w ~92% zgłoszeń, do tego nazwiska w treści komentarzy), a przy **34 instytucjach**
  Dokusa anonimizacja nazwy instytucji jest iluzoryczna — kontekst zgłoszenia i tak zdradza,
  o kogo chodzi. Realny wybór jest więc między pełną anonimizacją treści a kontrolą dostępu,
  nie między „ukryjemy nazwę" a resztą.
- **Hasła w zrzucie źródłowym** — zgłosić klientowi, że `konsultant.haslo` i `uzytkownik.haslo`
  to 32-znakowe hashe MD5 (bez bcrypt/argon), a `skrzynka_email.password` leży obok. Nas to nie
  dotyczy (adapter tych kolumn nie czyta), ale zrzut u nas na dysku owszem — trzymać go krótko
  i nie kopiować.
- **Odświeżanie korpusu** — mamy jednorazowy zrzut z 2026-07-24. Bez ustalonego trybu
  odświeżania (kolejny zrzut? dostęp read-only?) baza wiedzy zestarzeje się przy ~500 nowych
  użytecznych zgłoszeniach rocznie.
- **Uwierzytelnianie API** — brak; endpointy są dziś otwarte w sieci compose.
- **Licencja PolDense (gemma)** — zweryfikować dopuszczalność użycia komercyjnego.
- **Persystencja feedbacku** (czy wdrożeniowiec zaakceptował propozycję) — bez tego nie
  zmierzymy realnej użyteczności na produkcji; to też moment na decyzję o MariaDB.
- **Backup `data/parsed/`** — jedyny niepowtarzalny artefakt (odtworzenie = ponowny koszt LLM).
- **Limity i koszty LLM** — brak budżetowania i rate-limitu na wywołania generacji.

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

- [~] **0. Fundament repo** — szkielet, na którym da się uruchomić testy i całą kompozycję;
  zero logiki domenowej. Kolejność idzie od rzeczy weryfikowalnych bez Dockera — compose na
  starcie nie ma czego uruchomić, więc daje tylko informację „kontener wstał".
  - [x] **0a. Pakiet i narzędzia** — `pyproject.toml` (pakietowanie, entry-point `dokus`,
    `--import-mode=importlib` w `addopts`, markery `integration`, `integration_qdrant`,
    `integration_embedder`, `llm_live`), `requirements-dev.txt`, `.venv`.
  - [x] **0b. Konfiguracja** — `Settings` (`api/app/config.py`) + `.env.example` +
    walidator „pusty/biały string → `None`" (pułapka z „Konfiguracja i deploy") + **test
    plumbingu configu**. Pierwszy realny test w repo, chodzi bez Dockera. Noga „compose
    `environment:`" tego testu dochodzi w 0e, razem z plikami compose.
  - [x] **0c. Usługa `api`** — `Dockerfile`, `.dockerignore`, `requirements.txt`, `main.py`
    z `/health`, middleware Request-ID, handlery wyjątków (osobny na `RequestValidationError`),
    szkielet CLI (`dokus --help`).
  - [x] **0d. Warstwa LLM** — `LLMClient` (interfejs) + `LLMCompletion` (tekst + użycie do logu),
    `FakeLLMClient` (odpowiedzi skryptowane, `calls` do asercji, wyczerpanie skryptu = `LLMError`),
    `get_llm_client()` z fail-fast + testy atrapy i fabryki. Realnego dostawcy nie podłączamy —
    pierwszy użytkownik pojawia się w etapie 5, ale abstrakcja istnieje wcześniej, żeby nikt
    w międzyczasie nie zaimportował SDK prosto do domeny.
  - [ ] **0e. Compose** — baza: `api` + `qdrant` + `embedder`-zaślepka + warstwa `prod`.
    Obrazy pinowane (tag + digest), ENV przez `environment:`. Kolejność: zaślepka musi
    istnieć, zanim compose ma co budować; test plumbingu na końcu, bo domyka pętlę
    `.env.example` ↔ compose ↔ `Settings`.
    - [x] **0e-1. Usługa `embedder` (backend `fake`)** — `embedder/` (Dockerfile, `.dockerignore`,
      `requirements.txt` — **bez** `sentence-transformers`), `embedder_app/main.py` z `/health`
      i `POST /embed`. Warstwa `encoding/` w kształcie lustrzanym wobec `app/llm/`: `Encoder`
      (interfejs, async, `model_name`/`dimension`), `FakeEncoder` (`EMBEDDING_BACKEND=fake`),
      `build_encoder()`/`get_encoder()` z fail-fast, `EncoderError`/`EncoderConfigError`.
      Wektor **deterministyczny per tekst** (sha256 → seed → wektor znormalizowany, długość
      z `EMBEDDING_VECTOR_SIZE`), bez wag modelu: progi, dedupe i routing nie mają prawa zależeć
      od modelu (→ „Testy"). Kontrakt endpointu już w kształcie docelowym — przyjmuje `mode`
      (`query`/`passage`/`sts`) i **ignoruje** go, bo mapowanie `mode` → prefiks jest cechą
      modelu i mieszka w implementacji. Handlery wyjątków i Request-ID jak w `api`, plus własny
      handler `EncoderError` → **503** (awaria backendu jest przejściowa — config padł już przy
      starcie — więc indeksacja ma się wycofać i ponowić, a nie porzucić zgłoszenie).
      Sprawdzian: dwa wywołania `/embed` na tym samym tekście = ten sam wektor (także po
      restarcie procesu); zły `EMBEDDING_BACKEND` = śmierć przy starcie, nie błąd w żądaniu.
    - [ ] **0e-2. Baza `docker-compose.yml` (dev)** — `api` (build `./api`, bind-mount
      `./api/app`, `command` z `--reload`, `data/` zamontowane pod artefakty z etapu 1),
      `embedder` (build `./embedder`), `qdrant` (wolumen nazwany na `/qdrant/storage`).
      `healthcheck` tylko tam, gdzie usługa ma własny `/health` (`api`, `embedder`) — bez
      `depends_on: service_healthy`, bo `/health` mówi wyłącznie o sobie.
      **Wyrównanie testów do reguły „kontrakt w procesie, wdrożenie po HTTP"** (→ „Testy"),
      możliwe dopiero tutaj, bo przed compose `api` nie ma czego odpytać po HTTP:
      `api` dostaje integracyjny smoke `/health` (dziś jedyny sprawdzian kryterium
      „`compose up` → 200" jest ręczny); testy kontraktowe embeddera (422 na brak/zły `mode`
      i pusty batch, kolejność w batchu) schodzą do unitów na `TestClient`, a po HTTP zostaje
      cienki smoke na usługę — `/health` + jedno `/embed`.
    - [ ] **0e-3. Warstwa `docker-compose.prod.yml`** — `include:` bazy (jeden `-f` podnosi
      łańcuch), zdjęcie bind-mountu przez `volumes: !reset []` i nadpisanie `command` bez
      `--reload`. Sprawdzian: `config` tej warstwy nie pokazuje montowania kodu z hosta.
    - [ ] **0e-4. Trzecia noga testu plumbingu configu** — parsuje pliki compose **jako dane**
      (`pyyaml` do `requirements-dev.txt`, bez Dockera) i pilnuje zgodności kluczy
      `environment:` ↔ `.env.example` ↔ pól `Settings` w obie strony.

  **Kryterium ukończenia** (sprawdzalne komendą, nie opinią):
  `pytest` przechodzi offline i nie rusza sieci · `ruff check .` czysto ·
  `docker compose up -d` → `/health` 200 i Qdrant odpowiada ·
  `docker compose config` pokazuje zinterpolowane ENV bez pustych stringów ·
  `docker compose -f docker-compose.prod.yml config` bez bind-mountu kodu ·
  `dokus --help` działa po `pip install -e .` ·
  **test plumbingu configu pada** po celowym przekręceniu nazwy w `.env.example`
  (kontrola negatywna — strażnik, którego nikt nie widział na czerwono, nie jest strażnikiem).
- [ ] **1. Kontrakt zgłoszenia** — `ParsedTicket` (Pydantic) + prompt parsujący w `prompts/` +
  `dokus tickets validate`; na tej podstawie parsujemy ręcznie pierwszą partię w czacie.
  **Rozstrzygnąć tu:** los `cause` i `confirmed` (brak źródła w bazie — patrz „Dane wejściowe")
  oraz czy `system` zostaje w schemacie mimo że w tym zakresie jest stałą.
- [ ] **2. Embedder jako usługa** — realny PolDense obok backendu `fake` z etapu 0: nowa
  implementacja `Encoder` (wagi, dobór wariantu, warstwa GPU, prefiksy trybów, `encode` przez
  `run_in_threadpool`, bo `sentence-transformers` jest synchroniczne) + wpis w fabryce;
  `embed_query/passage/sts` i `EmbeddingClient` po stronie `api`. Dochodzą dwie reguły:
  **fabryka porównuje wymiar zgłoszony przez backend z `EMBEDDING_VECTOR_SIZE`** i wywala przy
  starcie (dziś ten sprawdzian nie ma jak paść — `fake` bierze wymiar z configu), oraz
  `EMBEDDING_MODEL` jako **parametr** jednej implementacji, nie osobny backend (PolDense, mmlw
  i BGE-M3 ładują się tak samo). **Otwarte:** czy `fake` zostaje jako backend do dev/CI, czy
  znika — decyzja po poznaniu rozmiaru wag i sprzętu.
- [ ] **3. Ewaluacja embeddera** — golden set par + `recall@5` na dwóch osiach: model (PolDense
  vs mmlw-roberta-large vs BGE-M3) i tryb (`query→passage` vs `sts→sts`, zapytanie surowe vs
  sparsowane); wynik zapisany w repo. **Decyzja o modelu i trybie zapada tu, nie wcześniej** —
  i to ona kasuje zbędny named vector.
- [ ] **4. Indeksacja** — filtr `resolved` + dedup + named vectors + payload;
  `dokus index build/rebuild` odtwarzalne z `data/parsed/`. Filtr jakości musi być mocniejszy
  niż sam status: warunek „ma opis i ma treść rozwiązania" (w źródle odsiewa 1496 z 1825).
- [ ] **5. Wyszukiwanie** — `POST /search`: parser zapytania (LLM → `ParsedTicket`) + top-K,
  próg, dedupe, zwrot trafień ze score i ID. **Tu parser wchodzi do runtime** — ten sam prompt
  i ten sam model Pydantic, którymi parsowaliśmy korpus.
- [ ] **6. Generacja propozycji** — prompt + routing 3-ścieżkowy + placeholdery; `POST /suggest`.
- [ ] **7. Masowy import w aplikacji** — adapter **SQL** (`ingest/`, źródłem jest zrzut bazy
  `helpdesk`, nie plik eksportu) + pipeline `RawTicket → LLM → ParsedTicket → data/parsed/`;
  parser z etapu 5 użyty ponownie, dochodzi wsadowość (wznawianie, limity, raport z przebiegu).
  Adapter skleja wątek: `zgloszenie` + jego `komentarz`e w kolejności `id`, po strip HTML.
  Skala przebiegu: ~1500 wywołań LLM — to jest ten „drogi, jednorazowy" koszt z zasady 7.
- [ ] **8. Rozszerzenia** — hybrid search (sparse pod kody błędów), reranker, frontend, feedback
  wdrożeniowców.
