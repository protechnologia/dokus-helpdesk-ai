from pathlib import Path

import pytest

from app.config import Settings
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_service.factory_tickets_importer import (
    TicketsImportConfigError,
    build_tickets_importer,
)
from app.engine_anonymization import AnonymizerClient
from app.engine_llm import LLMConfigError

# Fabryka serwisu masowego importu: z czego serwis powstaje i kiedy go nie ma. Bez usług — budowa
# klientów z nikim się nie łączy.


def _settings(**overrides: object) -> Settings:
    """
    Description:
    Konfiguracja z prawdziwym dostawcą modelu, kluczem i modelem, bez pliku `.env`, z podanymi
    zmianami.

    Example args:
        llm_generation_provider="fake"

    Example result:
        Settings(llm_generation_provider="openai", llm_generation_model="gpt-6.1-sol", …)
    """
    fields = {
        "_env_file":               None,
        "llm_generation_provider": "openai",
        "llm_generation_api_key":  "sk-test",
        "llm_generation_model":    "gpt-6.1-sol",
        **overrides,
    }

    return Settings(**fields)


async def test_the_importer_stands_on_the_configured_model_and_anonymizer() -> None:
    """Sprawdza, czy serwis importu dostaje podany korpus i liczbę zgłoszeń naraz, zapisuje
    w raporcie model z `LLM_GENERATION_MODEL` i stoi na kliencie usługi `anonymizer` z adresu
    z konfiguracji, bez zgody na atrapę silnika.

    Wyłapuje fabrykę, która bierze korpus, model albo anonimizator skądinąd niż z konfiguracji,
    albo przyjmuje wynik atrapy silnika anonimizacji: karty powstawałyby nie tym modelem, raport
    kłamałby, którym, a tekst bez anonimizacji poszedłby do modelu zewnętrznego."""
    corpus   = TicketsCorpus(root=Path("/dane/korpus"))
    importer = build_tickets_importer(
        _settings(anonymization_base_url="http://anonimizator:8000"), corpus, concurrency=3
    )

    try:
        assert importer._corpus      == corpus
        assert importer._concurrency == 3
        assert importer._model       == "gpt-6.1-sol"
        assert isinstance(importer._anonymizer, AnonymizerClient)
        assert str(importer._anonymizer._client.base_url).rstrip("/") == "http://anonimizator:8000"
        assert importer._anonymizer._fake_engine_allowed is False
    finally:
        await importer.aclose()


@pytest.mark.parametrize("provider", ["fake", " Fake "])
def test_the_fake_model_is_refused(provider: str) -> None:
    """Sprawdza, czy przy atrapie modelu generującego (także zapisanej z wielkiej litery i ze
    spacjami) fabryka odmawia błędem `TicketsImportConfigError`.

    Wyłapuje import na atrapie: atrapa grafu karty oddaje zawsze tę samą zmyśloną kartę,
    a anonimizator przyjmuje wtedy tekst bez zmian, więc do korpusu trafiłyby fałszywe karty
    i dane osobowe."""
    with pytest.raises(TicketsImportConfigError):
        build_tickets_importer(
            _settings(llm_generation_provider=provider), TicketsCorpus(root=Path("/k")), 4
        )


def test_a_model_without_a_key_is_refused_at_build_time() -> None:
    """Sprawdza, czy prawdziwy dostawca bez klucza kończy budowę błędem `LLMConfigError`, zanim
    import ruszy.

    Wyłapuje fabrykę, która odkłada błąd konfiguracji do pierwszego wywołania: komenda wypisałaby
    zakres i ruszyła, żeby przy każdym zgłoszeniu skończyć się tym samym błędem."""
    with pytest.raises(LLMConfigError):
        build_tickets_importer(
            _settings(llm_generation_api_key=None), TicketsCorpus(root=Path("/k")), 4
        )
