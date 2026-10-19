from app.agent_graphs.base import GraphState
from app.core_model.graphs.proposal import Proposal
from app.entry_routers.mapping import to_log_items, to_source_items, to_usage_item
from app.entry_routers.suggest.models import SuggestResponse

# Stan końcowy grafu `suggest_<wariant>` na odpowiedź `POST /suggest`: jeden kształt dla każdego
# wariantu. Osobno od trasy, bo tę samą odpowiedź złoży każda droga, którą trasa oddaje wynik.


def to_suggest_response(
    final:   GraphState,  # np. SuggestQuestionsState(…, sources=[…], output=Proposal(…))
    variant: str,         # np. "questions"
) -> SuggestResponse:
    """
    Description:
    Zamienia stan końcowy grafu wariantu na odpowiedź trasy. Stan jest typowany klasą bazową, bo
    wariant to dowolny graf z rejestru, a pola `output` i `sources` ma każdy własne.

    Treść dla klienta jest tylko w pełnej propozycji (`Proposal`). Same uwagi (`ProposalNotes`)
    oddaje wariant wymagający źródeł bez odczytanych źródeł i wariant z pytaniami, gdy pytań już
    nie trzeba: `text` jest wtedy `None`, a uwagi zostają. Gdy graf nie zostawił nawet uwag,
    wracają puste. Wariant bez narzędzi wiedzy nie ma pola `sources` i wraca z pustą listą.

    Example args:
        final=SuggestQuestionsState(input_text="ZGŁOSZENIE 41002…", sources=[SourceRef(…)],
                                    output=Proposal(text="1. Od kiedy…", internal_notes="1: …"))
        variant="questions"

    Example result:
        SuggestResponse(variant="questions", text="1. Od kiedy…", internal_notes="1: …",
                        sources=[SourceItem(…)])
    """
    output         = final.output
    text           = output.text if isinstance(output, Proposal) else None
    internal_notes = output.internal_notes if output is not None else ""

    response = SuggestResponse(
        variant        = variant,
        text           = text,
        internal_notes = internal_notes,
        sources        = to_source_items(getattr(final, "sources", [])),
        usage          = to_usage_item(final.usage),
        log            = to_log_items(final.log),
    )

    return response
