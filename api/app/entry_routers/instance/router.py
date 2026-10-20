from fastapi import APIRouter, Depends

from app.agent_graphs.factory import process_anonymizer
from app.config import Settings
from app.core_service.factory_index_inspector import get_index_inspector
from app.core_service.inspector_indexes import IndexInspector
from app.engine_anonymization import Anonymizer
from app.entry_routers.instance.mapping import to_instance_response
from app.entry_routers.instance.models import InstanceResponse

router = APIRouter(tags=["instance"])


@router.get("/instance", response_model=InstanceResponse)
async def read_instance(
    inspector:  IndexInspector = Depends(get_index_inspector),
    anonymizer: Anonymizer     = Depends(process_anonymizer),
) -> InstanceResponse:
    """
    Description:
    Na czym stoi instancja: model generujący, anonimizator (silnik i model z usługi `anonymizer`
    albo „niedostępny") i stan każdego indeksu, na którym stoją narzędzia agenta — brak, pusty albo
    ile elementów — liczony przy każdym żądaniu, więc nowy indeks widać bez restartu. W
    przeciwieństwie do `/health` mówi o dostawcy i modelu, ale nie o adresach ani kluczach; trasy
    nie są jeszcze chronione (p. 36).

    Example args:
        inspector=IndexInspector(…)
        anonymizer=process_anonymizer()

    Example result:
        InstanceResponse(model=GenerationModelInfo(provider="openai", name="gpt-6.1-sol"),
                         anonymization=AnonymizationInfo(state="available", engine="agent", …),
                         indexes=[IndexItem(material="tickets", index="cards", state="built",
                                            count=171), …],
                         code_package=CodePackageItem(branch="/main/stage-gminy", …))

    Raises:
        DbQdrantError, DbPostgresError: baza nie odpowiedziała — handler oddaje 503
    """
    report    = await inspector.inspect()
    described = await anonymizer.describe()
    response  = to_instance_response(Settings().llm_generation(), described, report)

    return response
