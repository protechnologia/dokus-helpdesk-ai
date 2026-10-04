from app.engine_llm.pricing.base import ModelPrice

# Model na własnym sprzęcie nie rozlicza tokenów, czymkolwiek jest serwowany — dziś Ollama, jutro
# vLLM albo Bielik na wynajętej karcie. Stawka to prawdziwe, zmierzone zero, a nie brakujący wiersz
# cennika, na którym cenniki dostawców głośno się wywalają.
#
# Nazwa pochodzi od tego, GDZIE model stoi, nie od narzędzia, które go serwuje: `client/ollama.py`
# jest jednym odbiorcą tej tabeli, a następny runner będzie kolejnym. Osobny plik zamiast wiersza
# w `pricing/openai.py`, bo tamta tabela to kopia opublikowanego cennika, którą się z nim
# sprawdza, a ta mówi coś o miejscu, w którym model działa.
#
# Budowane z pominięciem walidacji: wiersz cennika wymaga stawek dodatnich, a tu zero jest
# prawdziwą ceną, nie pomyłką.
FREE = ModelPrice.model_construct(
    input_per_million      = 0.0,
    output_per_million     = 0.0,
    cache_read_multiplier  = 1.0,
    cache_write_multiplier = 1.0,
)


def price_of(model: str) -> ModelPrice:   # np. "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
    """
    Description:
    Wycenia każdy model na własnym sprzęcie na zero. Przyjmuje dowolny identyfikator celowo:
    lokalny tag nazywa wydawcę, liczbę parametrów i kwantyzację, a pobranie nowego nic nie
    kosztuje — lista dozwolonych blokowałaby przebieg bez powodu, a ryzyka, przed którym chroni
    u dostawców (prawdziwy rachunek pokazany jako 0,00 USD), tutaj nie ma.

    Example args:
        model="SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"

    Example result:
        ModelPrice(input_per_million=0.0, output_per_million=0.0, cache_read_multiplier=1.0,
                   cache_write_multiplier=1.0)
    """
    return FREE


def calculate_cost_usd(
    model:              str,      # np. "SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
    prompt_tokens:      int,      # np. 4820
    completion_tokens:  int,      # np. 640
    cache_write_tokens: int = 0,  # np. 0 — lokalne runnery nie podają liczników cache
    cache_read_tokens:  int = 0,  # np. 0
) -> float:
    """
    Description:
    Podaje koszt jednego wywołania modelu na własnym sprzęcie: zawsze zero. Sygnatura jest taka
    sama jak w cennikach dostawców, żeby klient mógł wołać dowolny, nie wiedząc, który trzyma.

    Prawdziwym kosztem lokalnego przebiegu jest CZAS, nie pieniądze — model 4,5B na CPU odpowiada
    w minutach, nie sekundach. Kolumna z kwotą nic tu nie mówi; liczy się czas wypisany obok.

    Example args:
        model="SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0"
        prompt_tokens=4820
        completion_tokens=640
        cache_write_tokens=0
        cache_read_tokens=0

    Example result:
        0.0  # USD — własny sprzęt nie rozlicza tokenów
    """
    return 0.0
