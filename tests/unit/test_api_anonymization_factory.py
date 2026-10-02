import pytest

from app.anonymization import AnonymizationConfigError, FakeAnonymizer, build_anonymizer
from app.config import Settings


def test_the_fake_llm_gets_the_fake_anonymizer() -> None:
    """`LLM_PROVIDER=fake` → atrapa anonimizatora: nic nie wychodzi poza proces."""
    settings = Settings(llm_provider="fake", _env_file=None)

    assert isinstance(build_anonymizer(settings), FakeAnonymizer)


def test_a_real_llm_without_a_real_anonymizer_refuses_to_start() -> None:
    """Prawdziwy dostawca LLM → błąd konfiguracji przy starcie: atrapa przepuszcza tekst bez
    zmian, więc z modelem zewnętrznym byłaby przeciekiem."""
    settings = Settings(llm_provider="openai", _env_file=None)

    with pytest.raises(AnonymizationConfigError):
        build_anonymizer(settings)


async def test_the_fake_passes_text_through_unchanged() -> None:
    """Atrapa → tekst bez zmian w `AnonymizedText` i zapis w `texts`: niczego nie anonimizuje,
    co jest dokładnie powodem, dla którego fabryka trzyma ją z dala od prawdziwego modelu."""
    anonymizer = FakeAnonymizer()

    result = await anonymizer.anonymize("Jan Kowalski zgłasza błąd")

    assert result.text      == "Jan Kowalski zgłasza błąd"
    assert anonymizer.texts == ["Jan Kowalski zgłasza błąd"]
