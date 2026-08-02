from app.util.time import format_duration


def test_short_runs_stay_in_seconds():
    """Poniżej 90 s → same sekundy; dzielenie na minuty nic by tu nie wyjaśniło."""
    assert format_duration(42.4) == "42s"


def test_seconds_are_rounded_not_truncated():
    """Ułamek sekundy → zaokrąglenie; 89,6 s to bliżej 90 niż 89."""
    assert format_duration(89.6) == "90s"


def test_longer_runs_switch_to_minutes():
    """Od 90 s → minuty i sekundy; tak wygląda zgłoszenie na modelu lokalnym."""
    assert format_duration(125) == "2min 05s"


def test_seconds_are_zero_padded_in_minutes():
    """Sekundy dopełnione zerem — inaczej „2min 5s" czyta się jak 2min 50s."""
    assert format_duration(125) == "2min 05s"


def test_corpus_length_runs_switch_to_hours():
    """Powyżej godziny → godziny i minuty; tyle trwa przebieg po korpusie."""
    assert format_duration(3847.2) == "1h 04min"


def test_exact_hour_reports_zero_minutes():
    """Równa godzina → jawne 00min, nie samo „1h"; szerokość wyniku zostaje stała."""
    assert format_duration(3600) == "1h 00min"


def test_zero_is_rendered_not_blank():
    """Zero sekund → „0s", nie pusty string; wiersz podsumowania ma zawsze coś pokazać."""
    assert format_duration(0) == "0s"
