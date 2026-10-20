import pytest

from app.entry_routers.instance.mapping import to_instance_response
from tests._helpers.instance.samples import (
    sample_index_report,
    sample_llm_settings,
    sample_package_info,
)


@pytest.mark.parametrize("provider", ["fake", " FAKE "], ids=["fake", "wielkie litery i spacje"])
def test_the_fake_model_has_no_name_even_when_one_is_configured(
    provider: str,  # wstrzykiwane przez pytest z listy w dekoratorze wyżej
) -> None:
    """Sprawdza, czy przy atrapie modelu odpowiedź podaje dostawcę `fake` bez nazwy modelu, także
    gdy w konfiguracji stoi nazwa prawdziwego modelu, a dostawca jest wpisany wielkimi literami
    ze spacjami.

    Wyłapuje belkę, która pokazuje „gpt-6.1-sol", choć odpowiada atrapa: deweloper trzyma nazwę
    prawdziwego modelu w `.env`, a fabryka grafów czyta dostawcę bez względu na wielkość liter
    i spacje."""
    llm = sample_llm_settings(provider, "gpt-6.1-sol")

    response = to_instance_response(llm, sample_index_report(None))

    assert (response.model.provider, response.model.name) == ("fake", None)


def test_a_real_model_is_named() -> None:
    """Sprawdza, czy przy prawdziwym dostawcy odpowiedź podaje dostawcę i nazwę modelu
    z konfiguracji.

    Wyłapuje belkę bez nazwy modelu, który naprawdę odpowiada: z pokazu nie dałoby się
    powiedzieć, na czym chodzi."""
    llm = sample_llm_settings("openai", "gpt-6.1-sol")

    response = to_instance_response(llm, sample_index_report(None))

    assert (response.model.provider, response.model.name) == ("openai", "gpt-6.1-sol")


def test_every_index_goes_out_field_by_field() -> None:
    """Sprawdza, czy każdy indeks raportu wychodzi w odpowiedzi w tej samej kolejności,
    z materiałem, nazwą indeksu, stanem i liczbą.

    Wyłapuje mapowanie, które gubi stan albo liczbę, przestawia indeksy albo bierze stan nie
    z raportu: belka pokazałaby inny materiał jako pusty niż ten, który jest pusty."""
    report = sample_index_report(sample_package_info())

    response = to_instance_response(sample_llm_settings("fake", None), report)

    assert [item.model_dump() for item in response.indexes] == [
        status.model_dump() for status in report.indexes
    ]


def test_the_code_package_goes_out_or_is_null() -> None:
    """Sprawdza, czy gałąź i dzień budowy paczki kodu przechodzą do odpowiedzi, a raport bez
    paczki daje w odpowiedzi `null`.

    Wyłapuje mapowanie, które gubi gałąź albo pada na raporcie bez paczki kodu — a taki raport
    daje każda instancja bez zbudowanej paczki."""
    llm = sample_llm_settings("fake", None)

    with_package    = to_instance_response(llm, sample_index_report(sample_package_info()))
    without_package = to_instance_response(llm, sample_index_report(None))

    assert with_package.code_package.model_dump() == sample_package_info().model_dump()
    assert without_package.code_package is None
