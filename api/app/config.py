from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseModel):
    """
    Description:
    Konfiguracja jednego modelu językowego: komplet ustawień jednej roli, wyjęty z `Settings`.

    Do czego:
    `Settings` trzyma dwa takie komplety, każdy pod własnym przedrostkiem zmiennych:
    `LLM_GENERATION_*` dla modelu, który pisze odpowiedzi w grafach, i `LLM_ANONYMIZATION_*` dla
    modelu, który pomaga anonimizatorowi. Fabryka klienta (`get_llm_client()`) dostaje jeden
    komplet i nie musi wiedzieć, której roli służy.

    `env_prefix` niesie przedrostek zmiennych tego kompletu tylko po to, żeby komunikat błędu
    nazwał właściwą zmienną: przy dwóch kompletach samo „brakuje klucza" nie mówi, którego.
    """

    model_config = ConfigDict(extra="forbid")

    env_prefix:        str         = Field(examples=["LLM_GENERATION_"])
    provider:          str         = Field(examples=["openai"])
    base_url:          str | None  = Field(examples=["https://api.openai.com/v1"])
    api_key:           str | None  = Field(examples=["sk-proj-...HNkA"])
    model:             str | None  = Field(examples=["gpt-5.4-mini"])
    temperature:       float       = Field(examples=[0.0])
    timeout_seconds:   float       = Field(examples=[60.0])
    num_ctx:           int         = Field(examples=[8192])
    max_output_tokens: int         = Field(examples=[1500])


class Settings(BaseSettings):
    """
    Description:
    Single source of truth for every runtime knob of the `api` service. Values come from the
    environment only (see CLAUDE.md -> rule 1); nothing here may be hardcoded at a call site.

    Flow:
        1. pydantic-settings collects values from the process environment (and `.env` on the
           host, which is a developer convenience — containers get plain `environment:` keys).
        2. `_drop_blank_values` removes keys whose value is an empty or whitespace-only string,
           so a blank from `docker compose` falls back to the default declared here instead of
           silently becoming `""`.
        3. Field types and defaults apply; a missing required value fails fast at construction.

    Field names map to ENV names by upper-casing: `qdrant_url` <- `QDRANT_URL`. The prefixes
    (`LLM_GENERATION_`, `LLM_ANONYMIZATION_`, `EMBEDDING_`, `QDRANT_`, `POSTGRES_`, `RAG_`,
    `AGENT_`) are the only namespacing — there is one `.env` for the whole compose project, not
    one per service.
    """

    # Przedrostek pól z limitami wywołań narzędzi; reszta nazwy pola to nazwa narzędzia.
    TOOL_CALL_LIMIT_PREFIX: ClassVar[str] = "agent_max_calls_"

    model_config = SettingsConfigDict(
        env_file       = ".env",  # host convenience only; resolved relative to the CWD
        extra          = "ignore",  # a shared .env holds keys other services care about
        case_sensitive = False,
    )

    # --- observability ---
    log_level: str = "INFO"                             # e.g. "DEBUG"

    # --- LLM: dwie osobne konfiguracje, po jednej na rolę ---
    # Każda rola ma własny komplet tych samych ośmiu ustawień i nic nie dziedziczy po drugiej.
    # Obie domyślnie stoją na atrapie, więc `up` i `pytest` nic nie wysyłają i nic nie kosztują.
    #
    # `num_ctx` i `max_output_tokens` to budżet kontekstu w tokenach. Dostawcy chmurowi oba
    # ignorują; liczą się przy modelu self-hosted (Ollama, vLLM), gdzie okno ustawiamy sami,
    # a pomyłka jest cicha: nadmiar ponad `num_ctx` serwer ucina bez błędu. Budżet odpowiedzi
    # jest odejmowany od okna, nie doliczany.

    # Rola generująca: model, który pisze odpowiedzi w grafach. Dostaje tekst po anonimizacji.
    llm_generation_provider:          str        = "fake"  # np. "openai"
    llm_generation_base_url:          str | None = None    # np. "https://api.openai.com/v1"
    llm_generation_api_key:           str | None = None    # np. "sk-proj-...HNkA"
    llm_generation_model:             str | None = None    # np. "gpt-5.4-mini"
    llm_generation_temperature:       float      = 0.0     # parsowanie zgłoszeń zawsze na 0
    llm_generation_timeout_seconds:   float      = 60.0    # sekundy
    llm_generation_num_ctx:           int        = 8192    # musi mieścić się w oknie modelu
    llm_generation_max_output_tokens: int        = 1500    # część `num_ctx`, nie dodatek

    # Rola anonimizująca: model, który pomaga anonimizatorowi rozpoznawać dane osobowe (p. 19).
    # Widzi SUROWY tekst zgłoszeń, więc to, co tu wpiszesz, jest decyzją o tym, dokąd ten tekst
    # trafia — ma to być model pod naszą kontrolą, nie dostawca komercyjny.
    llm_anonymization_provider:          str        = "fake"  # np. "ollama"
    llm_anonymization_base_url:          str | None = None    # np. "http://ollama:11434/v1"
    llm_anonymization_api_key:           str | None = None    # Ollama klucza nie potrzebuje
    llm_anonymization_model:             str | None = None    # np. "model-lokalny:tag"
    llm_anonymization_temperature:       float      = 0.0     # rozpoznawanie ma być powtarzalne
    llm_anonymization_timeout_seconds:   float      = 60.0    # sekundy
    llm_anonymization_num_ctx:           int        = 8192    # musi mieścić się w oknie modelu
    llm_anonymization_max_output_tokens: int        = 1500    # część `num_ctx`, nie dodatek

    # --- embedder service (own compose service, reached over REST) ---
    embedding_base_url:        str   = "http://embedder:8000"
    embedding_vector_size:     int   = 768              # must match the Qdrant collection
    # Sized for the SLOWEST call — an indexing batch against a cold model, not a runtime query.
    embedding_timeout_seconds: float = 120.0            # seconds

    # --- Qdrant ---
    qdrant_url:              str   = "http://qdrant:6333"
    qdrant_collection:       str   = "tickets"
    # Kolekcja dokumentacji: fragmenty sekcji instrukcji, obok kolekcji zgłoszeń.
    qdrant_docs_collection:  str   = "docs"
    qdrant_timeout_seconds:  float = 30.0               # seconds

    # --- Postgres: indeks wyszukiwania tekstowego (od p. 29 także reguły bramek) ---
    # Host i port po stronie sieci compose. Hasło nie ma wartości w kodzie: compose podaje
    # dev-ową, a klient bazy odmawia startu bez niej.
    postgres_host:            str        = "postgres"
    postgres_port:            int        = 5432
    postgres_db:              str        = "helpdesk"
    postgres_user:            str        = "helpdesk"
    postgres_password:        str | None = None         # np. "helpdesk"
    postgres_timeout_seconds: float      = 30.0         # sekundy: łączenie i każde zapytanie

    # --- kod aplikacji: paczka dla narzędzi agenta ---
    # Katalog paczki zbudowanej przez `scripts/build_code_package.py` (kod w `repo/`, obok
    # `manifest.json`), po stronie kontenera. Montuje go compose, tylko do odczytu; zmiana tej
    # wartości montowania nie przestawia. Nie jest sprawdzany przy starcie: brak paczki wychodzi
    # przy pierwszym użyciu narzędzia kodu.
    code_package_dir: Path = Path("/code/data/unsafe/code")

    # --- retrieval: tuning, NOT business logic ---
    # These two are knobs a deployment turns; the rules that read them are not. Scoring the hits
    # and mapping a score onto a suggested variant stay in code, because that is a judgement about
    # answer quality rather than a setting (CLAUDE.md -> "Konfiguracja i deploy").
    #
    # Top 5 because more dilutes the answer: the generation prompt is built from 1-3 records, and
    # this is the pool the threshold narrows down to them.
    # Ta sama liczba ogranicza wynik obu wyszukiwań w dokumentacji: tyle sekcji oddaje jedno.
    rag_top_k:     int   = 5                            # e.g. 10
    # Measured 2026-08-20 on 171 records (data/unsafe/docs/pomiar-progu-score.md): 0.48 keeps 157 of
    # 162 correct hits and fully silences 14 of 16 distractors. The trade leans towards cutting
    # rubbish on purpose — with 47% of the corpus being singletons, "found nothing" is a normal
    # answer, while a contentless hit looks like an answer and is worse than none.
    # KNOWN COST: four correct hits drop out and THREE of them sat at rank 1, because short texts on
    # both sides score low however well they match — so this threshold systematically penalises the
    # shortest records. Do NOT raise without re-measuring: 0.50 takes four more.
    rag_score_min: float = 0.48                         # cosine similarity, range -1.0 .. 1.0
    # Najwyżej tyle znaków ma fragment sekcji dokumentacji, z którego powstaje jeden wektor.
    # Zmierzone 2026-10-05 na paczce syntetycznej: przy 1000 szczegół z końca najdłuższej sekcji
    # stoi pierwszy z zapasem 0,058, przy 1500 przegrywa o 0,004, a jeden wektor na sekcję gubi
    # go poza pierwszą piątką. Paczka ma jedną długą sekcję, więc wartość wraca do pomiaru na
    # właściwej dokumentacji. Zmiana wymaga ponownego `helpdesk docs index`.
    rag_docs_fragment_chars: int = Field(default=1000, ge=1)
    # Minimalne podobieństwo sekcji dokumentacji do zapytania — osobne od `rag_score_min`, bo
    # sekcja i karta zgłoszenia to inne teksty. Zmierzone 2026-10-05 na paczce syntetycznej:
    # zapytania z odpowiedzią mają 0,37–0,60, bez odpowiedzi 0,33–0,39; 0.37 zachowuje wszystkie
    # 24 i wycisza 4 z 5. Wybór po stronie zachowania trafień: model dostaje opis sekcji, nie
    # treść, więc słabe trafienie odrzuci sam, a brakującego nie odzyska. Wartość wstępna.
    rag_docs_score_min: float = 0.37                    # cosinus, zakres -1.0 .. 1.0

    # --- agent: limity wywołań narzędzi w jednym przebiegu grafu ---
    # Ile razy model może wywołać dane narzędzie przy jednej sprawie. Chroni przed pętlą, która
    # zużywa tokeny bez końca: wywołanie ponad limit dostaje błąd zamiast wyniku, a model ma
    # odpowiedzieć na podstawie tego, co już ma. Ten sam limit stoi w opisie narzędzia dla modelu.
    # Wyszukiwania mają po 5: oddają kilkadziesiąt tokenów, a jedno wywołanie tekstowe to jedna
    # fraza — zgłoszenie niesie ich bywa kilka: kod z ekranu, kod z logów, komunikat. Karty też 5,
    # bo są krótkie. Odczyt wątków i sekcji oddaje tysiące tokenów, więc ma po 3; wątek czyta się
    # po jednym na wywołanie, więc jego limit jest wprost liczbą wątków na sprawę.
    # Pole na narzędzie, o nazwie `agent_max_calls_<narzędzie>` — z niej składa się
    # `tool_call_limits()`, więc nowe narzędzie to nowe pole tutaj.
    agent_max_calls_find_tickets_vector: int = Field(default=5, ge=1)
    agent_max_calls_find_tickets_text:   int = Field(default=5, ge=1)
    agent_max_calls_read_tickets_card:   int = Field(default=5, ge=1)
    agent_max_calls_read_tickets_thread: int = Field(default=3, ge=1)
    agent_max_calls_list_docs:           int = Field(default=1, ge=1)
    agent_max_calls_find_docs_vector:    int = Field(default=5, ge=1)
    agent_max_calls_find_docs_text:      int = Field(default=5, ge=1)
    agent_max_calls_read_docs:           int = Field(default=3, ge=1)
    # Cytowanie kodu: jedno wywołanie to jeden fragment, więc limit jest liczbą cytowań w sprawie.
    agent_max_calls_quote_code:          int = Field(default=5, ge=1)

    # --- agent: limit tur modelu w jednym przebiegu grafu ---
    # Ile razy model może odpowiedzieć przy jednej sprawie w grafie z narzędziami. Gdy w ostatniej
    # dozwolonej turze nadal woła narzędzia, przebieg ich nie wykonuje, tylko idzie do odpowiedzi.
    # Domyka to, czego limity narzędzi nie domykają: wywołanie ponad limit narzędzia dostaje
    # odmowę, ale turę zużywa, więc model wołający w kółko zużywałby tokeny bez końca.
    # 20 to zapas, nie cel: sprawa w sondach z 2026-10-04 to 4–7 tur, a limity narzędzi pozwalają
    # na 32 wywołania, które model zwykle grupuje po kilka na turę. Ucięcie sprawy kosztuje
    # więcej niż kilka tur zapasu.
    agent_max_iterations: int = Field(default=20, ge=1)

    @model_validator(mode="before")
    @classmethod
    def _drop_blank_values(cls, values: Any) -> Any:    # e.g. {"llm_generation_model": "  "}
        """
        Description:
        Drops keys whose value is an empty or whitespace-only string, so the field falls back to
        its default. `docker compose` substitutes an EMPTY STRING for an undefined `${VAR:-}`,
        which without this would produce `Client(base_url="")` — a connection error at request
        time instead of a readable configuration error at startup.

        Example args:
            values={"qdrant_url": "", "llm_generation_model": "gpt-5.4-mini"}

        Example result:
            {"llm_generation_model": "gpt-5.4-mini"}
        """
        # Sources normally hand over a dict; anything else is passed through untouched.
        if not isinstance(values, dict):
            return values

        return {
            key: value
            for key, value in values.items()
            if not (isinstance(value, str) and value.strip() == "")
        }

    def llm_generation(self) -> LLMSettings:
        """
        Description:
        Konfiguracja modelu generującego — tego, który pisze odpowiedzi w grafach — jako jeden
        komplet dla fabryki klienta.

        Example args:
            (brak)

        Example result:
            LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", model="gpt-5.4-mini", …)
        """
        llm = LLMSettings(
            env_prefix        = "LLM_GENERATION_",
            provider          = self.llm_generation_provider,
            base_url          = self.llm_generation_base_url,
            api_key           = self.llm_generation_api_key,
            model             = self.llm_generation_model,
            temperature       = self.llm_generation_temperature,
            timeout_seconds   = self.llm_generation_timeout_seconds,
            num_ctx           = self.llm_generation_num_ctx,
            max_output_tokens = self.llm_generation_max_output_tokens,
        )

        return llm

    def llm_anonymization(self) -> LLMSettings:
        """
        Description:
        Konfiguracja modelu anonimizującego — tego, który pomaga anonimizatorowi i widzi surowy
        tekst zgłoszeń — jako jeden komplet dla fabryki klienta.

        Example args:
            (brak)

        Example result:
            LLMSettings(env_prefix="LLM_ANONYMIZATION_", provider="ollama", …)
        """
        llm = LLMSettings(
            env_prefix        = "LLM_ANONYMIZATION_",
            provider          = self.llm_anonymization_provider,
            base_url          = self.llm_anonymization_base_url,
            api_key           = self.llm_anonymization_api_key,
            model             = self.llm_anonymization_model,
            temperature       = self.llm_anonymization_temperature,
            timeout_seconds   = self.llm_anonymization_timeout_seconds,
            num_ctx           = self.llm_anonymization_num_ctx,
            max_output_tokens = self.llm_anonymization_max_output_tokens,
        )

        return llm

    def tool_call_limits(self) -> dict[str, int]:
        """
        Description:
        Limity wywołań narzędzi agenta jako mapa nazwa narzędzia → limit, złożona z pól
        `agent_max_calls_<narzędzie>`. Z niej korzysta węzeł `run_tools` (egzekwuje) i opis
        narzędzia dla modelu (mówi, ile wywołań ma do dyspozycji).

        Example args:
            (brak)

        Example result:
            {"find_tickets_vector": 3, "find_tickets_text": 3, "read_tickets_card": 3, …}
        """
        prefix = self.TOOL_CALL_LIMIT_PREFIX

        limits = {
            name.removeprefix(prefix): getattr(self, name)
            for name in type(self).model_fields
            if name.startswith(prefix)
        }

        return limits
