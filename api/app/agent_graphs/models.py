from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent_nodes import LogEntry
from app.engine_llm import LLMUsage


class ToolCallRun(BaseModel):
    """
    Description:
    Jedno wywołanie narzędzia w kroku `run_tools`: co model zlecił, co dostał w odpowiedzi i ile
    to trwało. Składa je `graph_step()` z trzech miejsc stanu — wywołania z tury modelu,
    wiadomości `tool` z wynikiem i pomiaru czasu — po wspólnym `call_id`.

    `result` to tekst, który dostał model, znak w znak: wynik narzędzia w JSON-ie albo błąd
    `{"error": …}`. Argumenty pisze model z tekstu po anonimizacji, a wynik pochodzi z indeksów,
    które model i tak czyta.
    """

    model_config = ConfigDict(extra="forbid")

    call_id:     str            = Field(min_length=1, examples=["call_1"])
    tool:        str            = Field(min_length=1, examples=["find_tickets_vector"])
    arguments:   dict[str, Any] = Field(default_factory=dict, examples=[{"problem": "…"}])
    result:      str            = Field(examples=['{"tickets": [], "dropped_below_threshold": 3}'])
    started_at:  datetime       = Field(examples=["2026-10-19T12:03:15.120000Z"])
    duration_ms: float          = Field(ge=0, examples=[84.2])


class GraphStep(BaseModel):
    """
    Description:
    Jeden krok przebiegu grafu, czyli jedno wywołanie węzła: który węzeł, kiedy zaczął, ile
    trwał, jego wpisy logu, a w turze modelu także zużycie tej tury i nazwy narzędzi, o które
    model w niej poprosił (`requested_tools`, z narzędziem odpowiedzi `respond_<graf>`). Krok
    `run_tools` niesie wywołania narzędzi z argumentami, wynikami i czasami.

    Do czego:
    `stream_graph()` oddaje kroki w trakcie przebiegu, więc wołający widzi, co dzieje się teraz,
    a nie dopiero `log` po fakcie. Krok zaczyna się tam, gdzie skończył się poprzedni, bo węzły
    grafu idą po kolei; pierwszy — przy starcie przebiegu.

    Surowej treści zgłoszenia ani odpowiedzi modelu tu nie ma, jak w `log`: krok `anonymize`
    niesie tekst po anonimizacji (`anonymized_text`) — ten sam, który czyta model — tura modelu
    tylko zużycie i nazwy zleconych narzędzi, bez argumentów, a odpowiedź grafu przychodzi
    osobno, ze stanem końcowym. Nazwy pozwalają wołającemu powiedzieć, co trwa po turze —
    narzędzia albo odpowiedź — bez czytania wpisu logu, który jest tekstem dla człowieka.
    """

    model_config = ConfigDict(extra="forbid")

    node:            str               = Field(min_length=1, examples=["agent"])
    started_at:      datetime          = Field(examples=["2026-10-19T12:03:14.902000Z"])
    duration_ms:     float             = Field(ge=0, examples=[2140.6])
    log:             list[LogEntry]    = Field(default_factory=list)
    usage:           LLMUsage | None   = None
    requested_tools: list[str]         = Field(default_factory=list, examples=[["read_docs"]])
    tool_calls:      list[ToolCallRun] = Field(default_factory=list)
    # Tylko w kroku `anonymize`: tekst zgłoszenia po anonimizacji, ten sam, który dostaje model.
    anonymized_text: str | None        = Field(default=None, examples=["{IMIĘ} zgłasza brak…"])
