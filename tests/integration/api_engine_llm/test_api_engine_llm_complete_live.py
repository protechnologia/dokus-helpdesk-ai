import asyncio

import pytest
from pydantic import BaseModel

from app.config import LLMSettings
from app.engine_llm import LLMCompletion, get_llm_client
from tests.conftest import live_generation_llm

pytestmark = pytest.mark.llm_live

# Prawdziwy model generujący z konfiguracji (`LLM_GENERATION_*`), wołany tą samą drogą co
# w produkcie: `Settings` -> `get_llm_client()` -> `complete()`. Testy sprawdzają to, czego żadna
# atrapa nie pokaże: czy dostawca przyjmuje żądanie w kształcie, w jakim wysyła je nasz klient,
# i czy z jego odpowiedzi da się odczytać tekst, zużycie i koszt.
#
# KOSZTUJE: jeden przebieg pliku to dwa krótkie wywołania modelu, policzone raz i wspólne dla
# wszystkich testów. Uruchamia się go świadomie, z folderem:
# `pytest tests/integration/api_engine_llm/ -m llm_live`. Innego dostawcę sprawdza się inną
# konfiguracją, nie zmianą w tym pliku. Bez `llm_live` w `-m` i przy atrapie modelu testy
# odmawiają (`live_generation_llm()` w `tests/conftest.py`).

# Dostawca self-hosted: nasz sprzęt nie nalicza tokenów, więc koszt wywołania to zero.
PROVIDER_SELFHOSTED = "ollama"

PLAIN_PROMPT = "Odpowiedz jednym krótkim zdaniem: ile dni ma tydzień?"

# Hasło stoi WYŁĄCZNIE w turze systemowej i ma polskie litery: odpowiedź, która je zawiera,
# dowodzi naraz, że tura systemowa dotarła do modelu i że polskie znaki przeszły w obie strony.
PASSWORD        = "żółw"
SYSTEM_PROMPT   = f"Odpowiadasz zawsze jednym słowem, małymi literami: {PASSWORD}."
PASSWORD_PROMPT = "Podaj hasło."


class LiveAnswers(BaseModel):
    """Odpowiedzi prawdziwego modelu zebrane raz na plik, razem z nazwą dostawcy z konfiguracji."""

    provider: str
    plain:    LLMCompletion
    password: LLMCompletion


async def _ask_the_model(
    llm: LLMSettings,  # np. Settings().llm_generation()
) -> LiveAnswers:
    """
    Description:
    Buduje klienta modelu z podanej konfiguracji i zadaje mu dwa pytania: zwykłe oraz takie, na
    które odpowiedź zna tylko z tury systemowej. To jedyne miejsce w pliku, które woła model.

    Example args:
        llm=LLMSettings(env_prefix="LLM_GENERATION_", provider="openai", model="gpt-5.4-mini", …)

    Example result:
        LiveAnswers(provider="openai", plain=LLMCompletion(text="Tydzień ma siedem dni.", …),
                    password=LLMCompletion(text="żółw", …))

    Raises:
        LLMError: dostawca odmówił, nie odpowiedział w czasie albo konfiguracja jest niepełna
    """
    client = get_llm_client(llm)

    answers = LiveAnswers(
        provider = llm.provider.strip().lower(),
        plain    = await client.complete(PLAIN_PROMPT),
        password = await client.complete(PASSWORD_PROMPT, system=SYSTEM_PROMPT),
    )

    return answers


@pytest.fixture(scope="module")
def answers(
    request: pytest.FixtureRequest,  # wstrzykiwane przez pytest; niesie wybór testów z `-m`
) -> LiveAnswers:
    """
    Description:
    Odpowiedzi prawdziwego modelu, policzone raz na plik (`_ask_the_model()`), żeby każdy test
    nie płacił za własne wywołanie. Konfigurację bierze przez `live_generation_llm()`, które
    odmawia, gdy testy wybrano bez jawnego `llm_live` albo gdy modelem jest atrapa.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        LiveAnswers(provider="openai", plain=LLMCompletion(…), password=LLMCompletion(…))
    """
    return asyncio.run(_ask_the_model(live_generation_llm(request.config)))


def test_the_configured_model_answers(answers: LiveAnswers) -> None:
    """Sprawdza, czy model generujący z konfiguracji odpowiada przez naszego klienta: na zwykłe
    pytanie wraca niepusty tekst, a odpowiedź niesie nazwę modelu i zmierzony czas wywołania.

    Wyłapuje żądanie, którego dostawca nie przyjmuje (parametr odrzucany przez ten model, zmieniony
    kształt API, zły klucz), oraz odpowiedź w kształcie, z którego klient nie umie wyjąć tekstu."""
    assert answers.plain.text.strip()
    assert answers.plain.model
    assert answers.plain.latency_ms > 0


def test_the_usage_of_the_call_is_counted(answers: LiveAnswers) -> None:
    """Sprawdza, czy z odpowiedzi dostawcy da się odczytać zużycie: wejście policzone w którejś
    z trzech klas (świeże, zapis do cache albo odczyt z cache) i co najmniej jeden token wyjścia.

    Wyłapuje klienta, który po zmianie formatu odpowiedzi czyta liczniki z niewłaściwych pól
    i zgłasza zera: koszt sprawy w odpowiedzi API wynosiłby wtedy zero bez żadnego błędu."""
    usage        = answers.plain
    input_tokens = usage.prompt_tokens + usage.cache_write_tokens + usage.cache_read_tokens

    assert input_tokens            > 0
    assert usage.completion_tokens > 0


def test_the_call_is_priced_like_its_provider(answers: LiveAnswers) -> None:
    """Sprawdza, czy wywołanie ma koszt właściwy dla dostawcy: większy od zera u dostawcy
    płatnego, a równy zeru przy modelu self-hosted, gdzie tokenów nikt nie nalicza.

    Wyłapuje wycenę, która przy prawdziwym, płatnym wywołaniu daje zero (model spoza cennika
    albo liczniki, których cennik nie widzi), oraz naliczanie kosztu za własny sprzęt."""
    if answers.provider == PROVIDER_SELFHOSTED:
        assert answers.plain.cost_usd == 0.0
        return

    assert answers.plain.cost_usd > 0


def test_the_system_turn_and_polish_letters_reach_the_model(answers: LiveAnswers) -> None:
    """Sprawdza, czy model odpowiada hasłem „żółw", które było podane wyłącznie w turze systemowej:
    na pytanie „Podaj hasło." w odpowiedzi stoi to słowo, z polskimi literami.

    Wyłapuje klienta, który gubi turę systemową albo wysyła ją w miejscu, którego model nie czyta
    jako instrukcji, oraz zepsute kodowanie polskich znaków w żądaniu albo w odpowiedzi."""
    assert PASSWORD in answers.password.text.lower()
