from app.agent_graphs.polish import PolishState
from app.entry_routers.mapping import to_log_items, to_usage_item
from app.entry_routers.polish.models import PolishResponse

# Stan końcowy grafu `polish` na odpowiedź `POST /polish`. Osobno od trasy, bo tę samą odpowiedź
# złoży każda droga, którą trasa oddaje wynik.


def to_polish_response(
    final: PolishState,  # np. PolishState(…, output=PolishedText(text="Dzień dobry, …"))
) -> PolishResponse:
    """
    Description:
    Zamienia stan końcowy grafu `polish` na odpowiedź trasy: poprawiony tekst, zużycie modelu
    i log przebiegu.

    Example args:
        final=PolishState(input_text="przesylki juz ida, kolejka stala", rules=["…"],
                          output=PolishedText(text="Dzień dobry, przesyłki już docierają…"))

    Example result:
        PolishResponse(text="Dzień dobry, przesyłki już docierają…", usage=UsageItem(…), log=[…])
    """
    response = PolishResponse(
        text  = final.output.text,
        usage = to_usage_item(final.usage),
        log   = to_log_items(final.log),
    )

    return response
