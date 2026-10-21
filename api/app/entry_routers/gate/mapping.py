from app.agent_graphs.gate_close import GateCloseState
from app.agent_graphs.gate_reply import GateReplyState
from app.entry_routers.gate.models import VerdictResponse
from app.entry_routers.mapping import to_log_items, to_usage_item

# Stan końcowy grafu bramki na odpowiedź `POST /gate/close` i `POST /gate/reply`: jeden kształt
# dla obu bramek. Osobno od trasy, bo tę samą odpowiedź złoży każda droga, którą trasa oddaje
# wynik.


def to_verdict_response(
    final:         GateCloseState | GateReplyState,  # np. GateCloseState(…, output=Verdict(…))
    rules_version: int,                              # np. 1
) -> VerdictResponse:
    """
    Description:
    Zamienia stan końcowy grafu bramki na odpowiedź trasy — werdykt z furtką, wersją zestawu
    reguł, zużyciem modelu i logiem przebiegu. Wersję podaje trasa, bo stan niesie same reguły.

    Example args:
        final=GateCloseState(input_text="ZGŁOSZENIE 41002…", rules=["…"],
                             output=Verdict(verdict="block", reasons=["…"], hint="Dopisz…"))
        rules_version=1

    Example result:
        VerdictResponse(verdict="block", …, overridable=True, rules_version=1)
    """
    verdict = final.output

    response = VerdictResponse(
        verdict       = verdict.verdict,
        reasons       = verdict.reasons,
        hint          = verdict.hint,
        rules_version = rules_version,
        usage         = to_usage_item(final.usage),
        log           = to_log_items(final.log),
    )

    return response
