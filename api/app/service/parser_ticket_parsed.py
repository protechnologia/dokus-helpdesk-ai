import json
import re

from pydantic import ValidationError

from app.llm.base import LLMClient
from app.model.ticket_parse_result import ParseResult
from app.model.ticket_parsed import ParsedTicket
from app.model.ticket_raw import RawTicket
from app.service.loader_dict_resolution import get_resolution_classes
from app.service.prompt_ticket_parse import build_parse_prompt, system_prompt
from app.util.validation_text import describe_validation_error

# Models wrap JSON in a markdown fence often enough that stripping it is part of reading the
# answer, not error handling. Tolerated rather than retried: the content is right, the packaging
# is not, and a retry would pay for the same answer twice.
_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)



def _strip_json_fence(text: str) -> str:   # e.g. "```json\n{\"problem\": \"…\"}\n```"
    """
    Description:
    Removes a markdown code fence around the answer, if the model added one.

    Example args:
        text="```json\\n{\\"problem\\": \\"Brak tonera\\"}\\n```"

    Example result:
        '{"problem": "Brak tonera"}'
    """
    return _JSON_FENCE.sub("", text).strip()


class TicketParser:
    """
    Description:
    Turns one source thread into a `ParsedTicket` using a language model. This is the step
    CLAUDE.md calls expensive and one-off (rule 7): its output is the durable artifact, while
    embeddings and Qdrant collections are disposable.

    Do czego:
    The same parser serves the batch import of stage 10 and the runtime query of stage 5, which is
    why it lives in the domain and takes an `LLMClient` through the constructor — the CLI and,
    later, the HTTP handler are thin adapters over it and hold no parsing logic of their own.

    Flow:
        1. `parse()` renders the thread and builds the prompt from the repo template plus the
           configured outcome vocabulary.
        2. The model answers; the answer is read as JSON.
        3. `ticket_id`, `date` and the vocabulary version are filled from the SOURCE, not from the
           answer — the model is never asked for them, so it cannot get them wrong.
        4. The result is validated against `ParsedTicket`. A rejected answer is reported as a
           failed `ParseResult`, with its cost, rather than raised.
    """

    def __init__(
        self,
        llm: LLMClient,  # e.g. ClaudeLLMClient(model="claude-haiku-4-5")
    ):
        """
        Description:
        Stores the transport client and reads the outcome vocabulary once, so a run over hundreds
        of tickets does not re-read the rules file per ticket.

        Example args:
            llm=ClaudeLLMClient(api_key="sk-ant-…", model="claude-haiku-4-5")

        Example result:
            TicketParser ready to answer `parse()`
        """
        self._llm        = llm
        self._vocabulary = get_resolution_classes()

    async def parse(
        self,
        raw: RawTicket,  # e.g. RawTicket(ticket_id="33644", subject="Błąd wysyłki", …)
    ) -> ParseResult:
        """
        Description:
        Parses one ticket. Never raises on a bad answer: the defect is reported in the result so a
        corpus run reports everything it could not parse instead of stopping at the first surprise.

        Example args:
            raw=RawTicket(ticket_id="33644", date=date(2026, 6, 23), subject="Błąd wysyłki", …)

        Example result:
            ParseResult(ticket_id="33644", ticket=ParsedTicket(…), cost_usd=0.0080)

        Raises:
            LLMError: the provider itself failed (timeout, no connection, refusal) — a transport
                failure is not a parsing verdict, so it stays an exception for the caller to
                decide about
        """
        prompt     = build_parse_prompt(thread=raw.as_thread(), vocabulary=self._vocabulary)
        completion = await self._llm.complete(prompt=prompt, system=system_prompt())

        # Accounting is attached first and kept on every return path below: a call that produced an
        # unusable answer cost exactly as much as one that worked.
        result = ParseResult(
            ticket_id         = raw.ticket_id,
            prompt_tokens     = completion.prompt_tokens,
            completion_tokens = completion.completion_tokens,
            cost_usd          = completion.cost_usd,
            latency_ms        = completion.latency_ms,
            model             = completion.model,
        )

        try:
            fields = json.loads(_strip_json_fence(completion.text))
        except json.JSONDecodeError as exc:
            result.errors = [f"odpowiedź modelu nie jest poprawnym JSON-em: {exc}"]

            return result

        # A model that answers with a list, or with a string, would otherwise fail later with a
        # message about a missing field — say what actually happened instead.
        if not isinstance(fields, dict):
            kind = type(fields).__name__
            result.errors = [f"odpowiedź modelu nie jest obiektem JSON, tylko {kind}"]

            return result

        # Identity comes from the SOURCE. The prompt never asks for these, so a model that invents
        # them anyway is caught by `extra="forbid"` — which is the point of that setting.
        fields["ticket_id"] = raw.ticket_id
        fields["date"]      = raw.date.isoformat()
        # Stamped from the vocabulary that actually built this prompt, so a later edit of the rules
        # cannot retroactively invalidate this artifact (CLAUDE.md -> "Domena").
        fields["resolution_vocabulary_version"] = self._vocabulary.version

        try:
            result.ticket = ParsedTicket.model_validate(fields)
        except ValidationError as exc:
            result.errors = describe_validation_error(exc)

        return result

