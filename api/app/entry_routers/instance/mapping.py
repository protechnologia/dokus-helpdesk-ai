"""
Description:
Zamienia konfigurację modelu generującego, opis anonimizatora (`AnonymizerInfo`) i stan
indeksów (`IndexReport`) na odpowiedź trasy `GET /instance`. Modele domeny nie wychodzą przez HTTP
wprost: każde pole jest przepisane.

Przed:

    llm        = LLMSettings(provider="fake", model="gpt-6.1-sol", …)
    anonymizer = AnonymizerInfo(available=False, engine=None, model=None)
    report     = IndexReport(
        indexes=[IndexStatus(material="docs", index="sections", count=None), …],
        code_package=None,
    )

Po:

    InstanceResponse(
        model=GenerationModelInfo(provider="fake", name=None),
        anonymization=AnonymizationInfo(state="unavailable", engine=None, model=None),
        indexes=[IndexItem(material="docs", index="sections", state="missing", count=None), …],
        code_package=None,
    )
"""

from app.config import LLMSettings
from app.core_model.instance.index_report import IndexReport
from app.engine_anonymization import AnonymizerInfo
from app.engine_llm.factory import PROVIDER_FAKE
from app.entry_routers.instance.models import (
    AnonymizationInfo,
    CodePackageItem,
    GenerationModelInfo,
    IndexItem,
    InstanceResponse,
)


def to_instance_response(
    llm:        LLMSettings,     # np. Settings().llm_generation()
    anonymizer: AnonymizerInfo,  # np. await process_anonymizer().describe()
    report:     IndexReport,     # np. await process_index_inspector().inspect()
) -> InstanceResponse:
    """
    Description:
    Składa odpowiedź `GET /instance` z konfiguracji modelu generującego, opisu anonimizatora
    i stanu indeksów. Przy atrapie modelu nazwy modelu nie podaje: atrapa jej nie używa, więc
    nazwa z `.env` mówiłaby nieprawdę o tym, co odpowiada.

    Example args:
        llm=LLMSettings(provider="openai", model="gpt-6.1-sol", …)
        anonymizer=AnonymizerInfo(available=True, engine="agent",
                                  model="speakleash/Bielik-11B-v3.0")
        report=IndexReport(indexes=[IndexStatus(material="tickets", index="cards", count=171), …],
                           code_package=CodePackageInfo(branch="/main", built_on=date(2026, 10, 7)))

    Example result:
        InstanceResponse(model=GenerationModelInfo(provider="openai", name="gpt-6.1-sol"),
                         anonymization=AnonymizationInfo(state="available", engine="agent",
                                                         model="speakleash/Bielik-11B-v3.0"),
                         indexes=[IndexItem(material="tickets", index="cards", state="built",
                                            count=171), …],
                         code_package=CodePackageItem(branch="/main", built_on=date(2026, 10, 7)))
    """
    # Wartość z ENV wpisuje człowiek: tak samo czyta ją fabryka grafów, wybierając atrapę.
    provider = llm.provider.strip().lower()
    name     = None if provider == PROVIDER_FAKE else llm.model

    indexes = [
        IndexItem(
            material = status.material,
            index    = status.index,
            state    = status.state,
            count    = status.count,
        )
        for status in report.indexes
    ]

    code_package = None

    if report.code_package is not None:
        code_package = CodePackageItem(
            branch   = report.code_package.branch,
            built_on = report.code_package.built_on,
        )

    anonymization = AnonymizationInfo(
        state  = "available" if anonymizer.available else "unavailable",
        engine = anonymizer.engine,
        model  = anonymizer.model,
    )

    response = InstanceResponse(
        model         = GenerationModelInfo(provider=provider, name=name),
        anonymization = anonymization,
        indexes       = indexes,
        code_package  = code_package,
    )

    return response
