"""
Description:
Próbki do testów mapowania trasy `GET /instance`: raport stanu indeksów ze wszystkimi trzema
stanami, opis anonimizatora i konfiguracja modelu generującego. Dzięki nim plik testu to same testy.

| co                      | do czego                                                      |
|-------------------------|---------------------------------------------------------------|
| `sample_package_info()` | gałąź i dzień budowy paczki kodu                              |
| `sample_index_report()` | raport: indeks zbudowany, pusty i brakujący oraz paczka kodu  |
| `sample_llm_settings()` | konfiguracja modelu generującego z podanym dostawcą i modelem |
| `sample_anonymizer()`   | opis anonimizatora: silnik `agent` z modelem albo niedostępny |

Każda próbka ma przedrostek `sample_`, więc w teście widać od razu, które wywołanie to dane
testu, a które kod aplikacji.

O czym pamiętać przy zmianach:

- Próbek nie wystawia `__init__.py` pakietu: test importuje je z tego modułu.
- Każda próbka powstaje od nowa przy wywołaniu, więc test, który ją zmieni, nie psuje innych.
"""

from datetime import date

from app.config import LLMSettings
from app.core_model.code.code_package_info import CodePackageInfo
from app.core_model.instance.index_report import IndexReport
from app.core_model.instance.index_status import IndexStatus
from app.engine_anonymization import AnonymizerInfo


def sample_package_info() -> CodePackageInfo:
    """
    Description:
    Paczka kodu z gałęzią i dniem budowy — tak wygląda paczka z kopii roboczej.

    Example args:
        (brak)

    Example result:
        CodePackageInfo(branch="/main/stage-gminy", built_on=date(2026, 10, 7))
    """
    return CodePackageInfo(branch="/main/stage-gminy", built_on=date(2026, 10, 7))


def sample_index_report(
    code_package: CodePackageInfo | None,  # np. sample_package_info(); None — paczki kodu nie ma
) -> IndexReport:
    """
    Description:
    Raport z każdym stanem indeksu: karty zbudowane, wątki puste, dokumentacji nie ma, kod
    zbudowany, z podanym opisem paczki kodu.

    Example args:
        code_package=sample_package_info()

    Example result:
        IndexReport(indexes=[IndexStatus(material="tickets", index="cards", count=171), …],
                    code_package=CodePackageInfo(branch="/main/stage-gminy", …))
    """
    report = IndexReport(
        indexes      = [
            IndexStatus(material="tickets", index="cards",     count=171),
            IndexStatus(material="tickets", index="threads",   count=0),
            IndexStatus(material="docs",    index="sections",  count=None),
            IndexStatus(material="docs",    index="fragments", count=None),
            IndexStatus(material="code",    index="package",   count=11424),
        ],
        code_package = code_package,
    )

    return report


def sample_llm_settings(
    provider: str,         # np. "openai"
    model:    str | None,  # np. "gpt-6.1-sol"
) -> LLMSettings:
    """
    Description:
    Konfiguracja modelu generującego z podanym dostawcą i modelem; reszta pól ma wartości, które
    na odpowiedź `GET /instance` nie wpływają.

    Example args:
        provider="openai"
        model="gpt-6.1-sol"

    Example result:
        LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", model="gpt-6.1-sol", …)
    """
    settings = LLMSettings(
        env_prefix        = "LLM_GENERATION_",
        provider          = provider,
        base_url          = None,
        api_key           = None,
        model             = model,
        temperature       = 0.0,
        timeout_seconds   = 60.0,
        num_ctx           = 8192,
        max_output_tokens = 1500,
    )

    return settings


def sample_anonymizer(
    available: bool,  # np. True; False — usługa `anonymizer` nie odpowiedziała
) -> AnonymizerInfo:
    """
    Description:
    Opis anonimizatora: silnik `agent` z modelem, a przy niedostępnej usłudze bez silnika
    i modelu — tak jak opisuje ją klient usługi.

    Example args:
        available=True

    Example result:
        AnonymizerInfo(available=True, engine="agent", model="speakleash/Bielik-11B-v3.0")
    """
    if not available:
        return AnonymizerInfo(available=False, engine=None, model=None)

    return AnonymizerInfo(available=True, engine="agent", model="speakleash/Bielik-11B-v3.0")
