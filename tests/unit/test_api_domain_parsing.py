import json
from datetime import date as Date

import pytest

from app.domain.parsing import TicketParser
from app.ingest.raw_ticket import RawComment, RawTicket
from app.llm import FakeLLMClient, LLMError
from app.rules.resolution import get_resolution_classes

# The fields the prompt asks for. `ticket_id`, `date` and the vocabulary version are deliberately
# absent: those come from the source, and a test that supplied them would not prove that.
MODEL_ANSWER = {
    "component":         "główna aplikacja",
    "problem":           "Wysyłka kończy się błędem komunikacji.",
    "symptoms":          "Po kliknięciu Wyślij pojawia się komunikat o braku sieci.",
    "error_codes":       ["ERR-4210"],
    "cause":             "Certyfikat bez uprawnienia AddDocumentToSign.",
    "solution":          "Wygenerowano certyfikat z właściwym uprawnieniem. Wykonuje dostawca.",
    "resolution":        "naprawione",
    "questions_summary": "brak",
}


def _answer(**overrides) -> str:
    """
    Description:
    Renders a model answer as JSON, with overrides applied. Each test then changes only the field
    it is about instead of restating the whole object.

    Example args:
        overrides={"cause": "  "}

    Example result:
        '{"component": "główna aplikacja", …, "cause": "  "}'
    """
    fields = dict(MODEL_ANSWER)
    fields.update(overrides)

    return json.dumps(fields, ensure_ascii=False)


def _raw(**overrides) -> RawTicket:
    """
    Description:
    Builds the source ticket handed to the parser.

    Example args:
        overrides={"ticket_id": "34287"}

    Example result:
        RawTicket(ticket_id="33644", date=date(2026, 6, 23), …)
    """
    values = {
        "ticket_id": "33644",
        "date":      Date(2026, 6, 23),
        "category":  "Błąd",
        "subject":   "Błąd wysyłki",
        "body":      "Nie działa wysyłka",
        "comments":  [
            RawComment(kind="rozwiazanie", role="konsultant",
                       created_at="2026-06-23 12:01:21", body="Wygenerowano certyfikat.")
        ],
    }
    values.update(overrides)

    return RawTicket(**values)


def _parser(*responses: str) -> TicketParser:
    """
    Description:
    Builds a parser over a scripted fake client, so no test reaches the network.

    Example args:
        responses=('{"problem": "…"}',)

    Example result:
        TicketParser(llm=FakeLLMClient([...]))
    """
    return TicketParser(FakeLLMClient(list(responses)))


async def test_valid_answer_produces_an_artifact():
    """Poprawna odpowiedź modelu → ParsedTicket bez błędów."""
    result = await _parser(_answer()).parse(_raw())

    assert result.ok
    assert result.ticket.problem  == MODEL_ANSWER["problem"]
    assert result.ticket.solution == MODEL_ANSWER["solution"]


async def test_identity_comes_from_the_source_not_the_model():
    """ticket_id i data wpisywane ze źródła — model nie jest o nie pytany."""
    result = await _parser(_answer()).parse(_raw(ticket_id="34287", date=Date(2026, 7, 15)))

    assert result.ticket.ticket_id == "34287"
    assert result.ticket.date      == Date(2026, 7, 15)


async def test_model_cannot_override_the_ticket_id():
    """Model podaje własne ticket_id → wygrywa wartość ze źródła, nie zmyślona."""
    # Kluczowe dla zasady 7: tożsamość rekordu nie może zależeć od tego, co wymyśli model.
    result = await _parser(_answer(ticket_id="99999")).parse(_raw(ticket_id="33644"))

    assert result.ok
    assert result.ticket.ticket_id == "33644"


async def test_records_the_vocabulary_version_used():
    """Artefakt zapisuje wersję słownika, którą powstał — bez niej edycja reguł unieważnia go."""
    result = await _parser(_answer()).parse(_raw())

    assert result.ticket.resolution_vocabulary_version == get_resolution_classes().version


async def test_markdown_fence_is_tolerated():
    """Odpowiedź w płotku ``` → sparsowana; treść jest dobra, opakowanie nie."""
    result = await _parser(f"```json\n{_answer()}\n```").parse(_raw())

    assert result.ok


async def test_non_json_answer_is_reported_not_raised():
    """Śmieć zamiast JSON-a → błąd w wyniku, nie wyjątek przerywający przebieg korpusu."""
    result = await _parser("nie jestem JSON-em").parse(_raw())

    assert not result.ok
    assert "JSON" in result.errors[0]


async def test_json_that_is_not_an_object_is_named_as_such():
    """Lista zamiast obiektu → komunikat mówi, co przyszło, nie o brakującym polu."""
    result = await _parser('["a", "b"]').parse(_raw())

    assert not result.ok
    assert "list" in result.errors[0]


async def test_blank_field_is_rejected():
    """Puste pole zamiast 'brak' → odrzucone; pusty string to pole pominięte, nie odpowiedź."""
    result = await _parser(_answer(cause="   ")).parse(_raw())

    assert not result.ok
    assert any("cause" in error for error in result.errors)


async def test_unknown_key_is_rejected():
    """Klucz spoza schematu → błąd, nie ciche odrzucenie (extra=forbid, zasada 7)."""
    result = await _parser(_answer(wymyslone_pole="cokolwiek")).parse(_raw())

    assert not result.ok
    assert any("wymyslone_pole" in error for error in result.errors)


async def test_resolution_outside_the_vocabulary_is_rejected():
    """resolution spoza słownika → odrzucone wobec wersji zapisanej w rekordzie."""
    result = await _parser(_answer(resolution="wymyslona_klasa")).parse(_raw())

    assert not result.ok
    assert any("resolution" in error for error in result.errors)


async def test_failed_parse_still_reports_its_cost():
    """Odrzucona odpowiedź → koszt i tokeny w wyniku; wywołanie kosztowało tyle samo co udane."""
    result = await _parser("nie jestem JSON-em").parse(_raw())

    assert not result.ok
    # Atrapa nic nie kosztuje, ale tokeny liczy — i to one dowodzą, że rozliczenie jest dołączane
    # także na ścieżce błędu, gdzie przy prawdziwym dostawcy byłyby realne pieniądze.
    assert result.prompt_tokens > 0
    assert result.model == "fake"


async def test_thread_reaches_the_prompt():
    """Wątek zgłoszenia trafia do promptu — inaczej model parsowałby pustkę."""
    llm    = FakeLLMClient([_answer()])
    parser = TicketParser(llm)

    await parser.parse(_raw(subject="Błąd wysyłki ePUAP"))

    assert "Błąd wysyłki ePUAP" in llm.calls[0].prompt


async def test_system_prompt_is_attached():
    """Prompt systemowy dołączony — to on ustawia rolę parsera i zakaz zmyślania."""
    llm = FakeLLMClient([_answer()])

    await TicketParser(llm).parse(_raw())

    assert llm.calls[0].system is not None
    assert "parserem zgłoszeń" in llm.calls[0].system


async def test_vocabulary_reaches_the_prompt():
    """Słownik rozstrzygnięć wstawiony do promptu jako dane — model ma z czego wybierać."""
    llm = FakeLLMClient([_answer()])

    await TicketParser(llm).parse(_raw())

    for entry in get_resolution_classes().classes:
        assert entry.name in llm.calls[0].prompt


async def test_provider_failure_propagates():
    """Awaria dostawcy → LLMError w górę; to nie werdykt o zgłoszeniu, tylko awaria transportu."""
    # FakeLLMClient bez scenariusza na drugie wywołanie zgłasza LLMError — tak samo jak timeout.
    parser = _parser(_answer())

    await parser.parse(_raw())

    with pytest.raises(LLMError):
        await parser.parse(_raw())
