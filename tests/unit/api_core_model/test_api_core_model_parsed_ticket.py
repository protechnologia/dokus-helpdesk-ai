import pytest
from pydantic import ValidationError

from app.core_model.tickets.parsed_ticket import NO_VALUE, NOT_APPLICABLE, ParsedTicket

# A record carrying real content, used as the starting point every test varies from.
VALID_TICKET = {
    "ticket_id":                     "33644",
    "date":                          "2026-03-14",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka przez ePUAP kończy się błędem komunikacji",
    "symptoms":                      "Po kliknięciu Wyślij pojawia się komunikat o braku sieci",
    "error_codes":                   ["ERR-4210"],
    "cause":                         "Certyfikat bez uprawnienia AddDocumentToSign",
    "solution":                      "Wygenerowano certyfikat z właściwym uprawnieniem.",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "pytano o wersję przeglądarki",
}


def test_valid_ticket_is_accepted() -> None:
    """Sprawdza, czy sparsowane zgłoszenie z wypełnionymi wszystkimi polami przechodzi walidację
    i zachowuje podane wartości — test patrzy na numer zgłoszenia i rodzaj rozstrzygnięcia.

    Wyłapuje model, który odrzuca poprawny rekord albo zmienia jego wartości: żaden plik
    z korpusu nie dałby się wtedy wczytać."""
    ticket = ParsedTicket(**VALID_TICKET)

    assert ticket.ticket_id  == "33644"
    assert ticket.resolution == "naprawione"


def test_record_of_pure_exits_is_valid() -> None:
    """Sprawdza, czy rekord, w którym przyczyna, rozwiązanie i podsumowanie pytań mają wartość
    `brak`, objawy `nie dotyczy`, a lista kodów błędów jest pusta, przechodzi walidację.

    Wyłapuje model, który jawne „nic tu nie ma" traktuje jak błąd: to zwykły stan zgłoszenia,
    a nie wada, i odrzucanie takich rekordów zmuszałoby do wpisywania zmyślonych wartości."""
    ticket = ParsedTicket(
        **{
            **VALID_TICKET,
            "cause":             NO_VALUE,
            "solution":          NO_VALUE,
            "symptoms":          NOT_APPLICABLE,
            "error_codes":       [],
            "questions_summary": NO_VALUE,
        }
    )

    assert ticket.cause    == NO_VALUE
    assert ticket.symptoms == NOT_APPLICABLE


def test_questions_summary_defaults_to_the_explicit_exit() -> None:
    """Sprawdza, czy rekord bez pola `questions_summary` (podsumowanie pytań konsultanta) dostaje
    w nim wartość `brak`.

    Wyłapuje zmianę albo usunięcie wartości domyślnej: zgłoszenia, w których konsultant o nic
    nie dopytywał, są częste, i rekord bez tego pola ma znaczyć „pytań nie było", a nie być
    błędem."""
    payload = {key: value for key, value in VALID_TICKET.items() if key != "questions_summary"}

    assert ParsedTicket(**payload).questions_summary == NO_VALUE


@pytest.mark.parametrize("field", ["component", "problem", "symptoms", "cause", "solution"])
def test_blank_text_is_rejected(field: str) -> None:
    """Sprawdza, czy tekst z samych spacji w każdym z pól `component`, `problem`, `symptoms`,
    `cause` i `solution` daje błąd walidacji.

    Wyłapuje przyjęcie pustego pola: brak wartości zapisuje się jawnie słowem `brak`, a puste
    pole to pole pominięte przez model, które w korpusie wyglądałoby jak wypełnione."""
    with pytest.raises(ValidationError):
        ParsedTicket(**{**VALID_TICKET, field: "   "})


def test_surrounding_whitespace_is_stripped() -> None:
    """Sprawdza, czy spacje na początku i na końcu wartości są obcinane: `problem` podany ze
    spacjami po obu stronach jest zapisany jako samo „Drukarka nie drukuje".

    Wyłapuje zapis wartości razem ze spacjami: ten sam tekst zapisany raz ze spacjami, a raz bez
    nich dałby w indeksie dwa różne wektory."""
    ticket = ParsedTicket(**{**VALID_TICKET, "problem": "  Drukarka nie drukuje  "})

    assert ticket.problem == "Drukarka nie drukuje"


def test_unknown_field_is_rejected() -> None:
    """Sprawdza, czy klucz, którego kontrakt zgłoszenia nie przewiduje (tu `severity`), daje błąd
    walidacji.

    Wyłapuje ciche kasowanie nadmiarowych pól: model parsujący potrafi dołożyć własne pole,
    a jego przebieg jest jednorazowy, więc treści skasowanej bez śladu nie da się odzyskać."""
    with pytest.raises(ValidationError):
        ParsedTicket(**{**VALID_TICKET, "severity": "wysoka"})


def test_resolution_outside_the_vocabulary_is_rejected() -> None:
    """Sprawdza, czy rodzaj rozstrzygnięcia spoza słownika (tu `zamkniete-bo-tak`) daje błąd
    walidacji.

    Wyłapuje brak kontroli wobec słownika: literówki i wartości wymyślone przez model weszłyby
    do korpusu jako osobne rodzaje rozstrzygnięć."""
    with pytest.raises(ValidationError):
        ParsedTicket(**{**VALID_TICKET, "resolution": "zamkniete-bo-tak"})


def test_record_from_another_vocabulary_version_is_rejected() -> None:
    """Sprawdza, czy rekord zapisany z inną wersją słownika rozstrzygnięć, niż ma ta instalacja
    (tu wersja 99), daje błąd walidacji, w którego treści jest ten numer wersji.

    Wyłapuje rekord z obcej wersji słownika oceniony dzisiejszym słownikiem oraz komunikat bez
    numeru wersji: po ponownym sparsowaniu korpusu tysiąc takich błędów wyglądałoby na
    niezwiązane ze sobą, choć mają jedną przyczynę."""
    with pytest.raises(ValidationError) as exc:
        ParsedTicket(**{**VALID_TICKET, "resolution_vocabulary_version": 99})

    # The message must say the vocabulary is out of step, not merely "invalid value" — otherwise
    # a whole re-parsed corpus looks like a thousand unrelated errors.
    assert "99" in str(exc.value)


def test_embedding_text_joins_only_problem_and_symptoms() -> None:
    """Sprawdza, czy tekst, z którego liczony jest wektor zgłoszenia, to dokładnie `problem`
    i `symptoms` w tej kolejności, każde w swojej linii, i nic więcej.

    Wyłapuje zmianę składu albo kolejności tego tekstu: wektory zapisane już w indeksie
    przestałyby pasować do nowo liczonych, a wyszukiwanie pogorszyłoby się bez żadnego błędu."""
    ticket = ParsedTicket(**VALID_TICKET)

    assert ticket.embedding_text() == f"{ticket.problem}\n{ticket.symptoms}"


def test_embedding_text_excludes_the_solution() -> None:
    """Sprawdza, czy rozwiązanie nie trafia do tekstu, z którego liczony jest wektor: rekord
    z rozwiązaniem `UNIKATOWAFRAZA` nie ma tego słowa w tekście do wektora.

    Wyłapuje dołożenie pola `solution` do wektora: szukamy po podobieństwie problemu, a wektor
    z domieszką rozwiązania mieszałby oba sygnały."""
    ticket = ParsedTicket(**{**VALID_TICKET, "solution": "UNIKATOWAFRAZA"})

    assert "UNIKATOWAFRAZA" not in ticket.embedding_text()


def test_artifact_records_the_vocabulary_version() -> None:
    """Sprawdza, czy rekord zamieniony na dane do zapisu (`model_dump()`) niesie wersję słownika
    rozstrzygnięć, z którą powstał — tu wersję 1.

    Wyłapuje zapis bez numeru wersji: po późniejszej zmianie słownika nie dałoby się ustalić,
    z którą wersją rekord powstał i które rekordy trzeba sparsować ponownie."""
    dumped = ParsedTicket(**VALID_TICKET).model_dump()

    assert dumped["resolution_vocabulary_version"] == 1
