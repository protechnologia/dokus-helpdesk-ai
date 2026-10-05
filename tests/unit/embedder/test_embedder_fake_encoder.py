from embedder_app.encoding import FakeEncoder, deterministic_vector

TICKET_TEXT       = "Drukarka nie drukuje po aktualizacji sterownika"
OTHER_TICKET_TEXT = "Terminal płatniczy zgłasza błąd E-104"


async def test_encode_returns_one_vector_per_text() -> None:
    """Sprawdza, czy atrapa kodera dla dwóch tekstów oddaje dwa wektory, w tej samej kolejności co
    teksty.

    Wyłapuje koder, który gubi wektor albo zmienia kolejność: wołający przypisuje wektory do tekstów
    po pozycji, więc zgłoszenie dostałoby wektor innego zgłoszenia."""
    encoder = FakeEncoder(dimension=16)

    vectors = await encoder.encode([TICKET_TEXT, OTHER_TICKET_TEXT], "passage")

    assert vectors == [
        deterministic_vector(TICKET_TEXT, 16),
        deterministic_vector(OTHER_TICKET_TEXT, 16),
    ]


async def test_encode_uses_the_configured_dimension() -> None:
    """Sprawdza, czy atrapa kodera zbudowana z wymiarem 32 oddaje wektor o długości dokładnie 32.

    Wyłapuje koder, który liczy wektory w innym wymiarze, niż mu ustawiono: kolekcja w Qdrancie
    przyjmuje tylko wektory o jednej, ustalonej długości."""
    encoder = FakeEncoder(dimension=32)

    vectors = await encoder.encode([TICKET_TEXT], "query")

    assert len(vectors[0]) == 32


async def test_mode_does_not_change_the_vector() -> None:
    """Sprawdza, czy atrapa kodera daje dla tego samego tekstu ten sam wektor w każdym z trzech
    trybów: `query`, `passage` i `sts`.

    Wyłapuje atrapę, w której tryb zaczął wpływać na wynik. Atrapa nie ma wytrenowanych prefiksów,
    więc jej wektor ma zależeć wyłącznie od tekstu; inaczej tekst zapisany w indeksie i ten sam
    tekst użyty jako zapytanie przestałyby do siebie pasować w testach wyszukiwania."""
    encoder = FakeEncoder(dimension=16)

    as_query   = await encoder.encode([TICKET_TEXT], "query")
    as_passage = await encoder.encode([TICKET_TEXT], "passage")
    as_sts     = await encoder.encode([TICKET_TEXT], "sts")

    assert as_query == as_passage == as_sts


async def test_encoder_reports_the_fake_model_name() -> None:
    """Sprawdza, czy atrapa kodera przedstawia się nazwą modelu „fake".

    Wyłapuje atrapę, która podaje się za prawdziwy model: po nazwie ma dać się rozpoznać, że wektory
    w kolekcji pochodzą z atrapy, bo nie da się ich porównywać z wektorami prawdziwego modelu."""
    encoder = FakeEncoder(dimension=16)

    assert encoder.model_name == "fake"


def test_encoder_reports_its_dimension() -> None:
    """Sprawdza, czy atrapa kodera zbudowana z wymiarem 768 zgłasza ten sam wymiar we właściwości
    `dimension`.

    Wyłapuje koder, który zgłasza inny wymiar, niż dostał: fabryka porównuje tę liczbę
    z konfiguracją, więc sprawdzałaby wtedy nieprawdziwą wartość."""
    assert FakeEncoder(dimension=768).dimension == 768
