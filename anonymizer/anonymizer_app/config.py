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
    # przepuści jego wyniku do prawdziwego modelu; każda inna nieznana wartość kończy start
    # usługi błędem konfiguracji.
    anonymization_engine: str = "fake"  # np. "fake"

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
        Settings(log_level="INFO", anonymization_engine="fake")
    """
    return Settings()
