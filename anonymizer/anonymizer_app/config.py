from functools import lru_cache
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Description:
    Ustawienia usługi `anonymizer`. Nazwy pól to nazwy zmiennych z `.env.example` pisane małymi
    literami — jeden kontrakt konfiguracji dla całego projektu compose, nie osobny na usługę
    (CLAUDE.md -> „Konfiguracja i deploy").

    Celowo bez czytania pliku `.env`: usługa dostaje wyłącznie klucze `environment:` z compose,
    tak jak `embedder`.
    """

    model_config = SettingsConfigDict(
        extra          = "ignore",  # wspólne środowisko niesie klucze innych usług
        case_sensitive = False,
    )

    # --- obserwowalność ---
    log_level: str = "INFO"             # np. "DEBUG"

    # --- anonimizacja ---
    # Silnik, który zamienia dane na znaczniki. `fake` oddaje tekst bez zmian, więc `api` nie
    # przepuści jego wyniku do prawdziwego modelu; `agent` to graf: wzorce i model anonimizujący.
    # Każda inna wartość kończy start usługi błędem konfiguracji. W kodzie domyślnie `fake`, żeby
    # test bez konfiguracji nie potrzebował modelu; compose i `.env.example` stawiają `agent`.
    anonymization_engine: str = "fake"  # np. "agent"

    # --- model anonimizujący: czyta go tylko silnik `agent` ---
    # Ten model widzi SUROWY tekst zgłoszeń, więc adres to decyzja o tym, dokąd ten tekst trafia.
    # Mówi Chat Completions zgodnym z OpenAI (vLLM, Ollama): innej drogi do modelu usługa nie ma,
    # dlatego nie ma też zmiennej z dostawcą.
    llm_anonymization_base_url:        str | None = None   # np. "https://…proxy.runpod.net/v1"
    llm_anonymization_api_key:         str | None = None   # vLLM bez `--api-key` go nie sprawdza
    llm_anonymization_model:           str | None = None   # np. "speakleash/Bielik-11B-v3.0-…"
    llm_anonymization_temperature:     float      = 0.0    # wskazywanie danych ma być powtarzalne
    llm_anonymization_timeout_seconds: float      = 60.0   # sekundy na jedno wywołanie modelu
    # Okno kontekstu SERWERA, nie żądanie: silnik sprawdza przy starcie, czy największa część
    # tekstu razem z promptem i odpowiedzią się w nim mieści.
    llm_anonymization_num_ctx:         int        = 16384  # np. 16384 — `max_model_len` w vLLM

    @model_validator(mode="before")
    @classmethod
    def _drop_blank_values(cls, values: Any) -> Any:  # np. {"anonymization_engine": " "}
        """
        Description:
        Pomija klucze z pustą wartością albo samymi spacjami, żeby pole wróciło do wartości
        domyślnej. `docker compose` wstawia pusty napis za niezdefiniowane `${VAR:-}`.
        Powielone z `api` i `embedder` celowo: usługi nie dzielą kodu, tylko kontrakt ENV.

        Example args:
            values={"anonymization_engine": "", "log_level": "DEBUG"}

        Example result:
            {"log_level": "DEBUG"}
        """
        # Źródła zwykle podają słownik; cokolwiek innego przechodzi bez zmian.
        if not isinstance(values, dict):
            return values

        kept = {
            key: value
            for key, value in values.items()
            if not (isinstance(value, str) and value.strip() == "")
        }

        return kept


@lru_cache
def get_settings() -> Settings:
    """
    Description:
    Buduje `Settings` raz na proces i oddaje tę samą instancję każdemu żądaniu. Pamiętane, a nie
    zbudowane przy imporcie modułu, żeby import nie czytał środowiska.

    Example args:
        (brak)

    Example result:
        Settings(log_level="INFO", anonymization_engine="agent", llm_anonymization_model="…", …)
    """
    return Settings()
