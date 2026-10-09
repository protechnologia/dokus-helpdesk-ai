from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.agent_tools.models import ExactText, MatchKind

# Najwyżej tyle linii oddaje jedno szukanie; pozostałe pasujące są tylko policzone. Dwadzieścia
# pozycji z treścią to około 1,4 tys. znaków, a częste słowo trafia w kodzie w tysiące linii.
MAX_LINES_PER_SEARCH = 20

# Najwyżej tyle znaków treści linii trafia do wyniku. Dłuższych jest w paczce 0,3%, a mediana
# trafionej linii to 40–70 znaków.
MAX_TEXT_CHARS = 200

# Najdłuższe słowo z `words` ma mieć co najmniej tyle znaków — ten sam próg co dla frazy
# (`ExactText`): krótsze trafia w kodzie w setki tysięcy linii.
MIN_LONGEST_WORD_CHARS = 3

# Słowa oddzielone spacją; spacje z brzegów są obcinane, a same spacje to brak słów.
SearchWords = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class FindCodeTextQuery(BaseModel):
    """
    Description:
    O co agent pyta `find_code_text`: tekst, który ma stać w linii kodu aplikacji, i opcjonalnie
    miejsce, do którego zawęzić szukanie. Pola `exact` i `words` znaczą to samo co
    w wyszukiwaniach tekstowych zgłoszeń i dokumentacji, żeby model pytał trzy narzędzia tak samo.
    """

    # Nieznany argument to błąd, jak w każdym modelu zapytania.
    model_config = ConfigDict(extra="forbid")

    # Jedna fraza, przepisana bez zmian: stały fragment komunikatu, kod błędu, nazwa z kodu.
    exact: ExactText | None   = Field(default=None, examples=["Brak sekwencji numeracji"])
    # Słowa po spacji; linia musi zawierać wszystkie. Bez odmiany: słowo to ciąg znaków.
    words: SearchWords | None = Field(default=None, examples=["sekwencji numeracji"])
    # Katalog albo plik w kodzie aplikacji; bez niego szukanie obejmuje cały kod.
    path:  str | None         = Field(default=None, min_length=1, examples=["src/web/js"])

    @model_validator(mode="after")
    def _is_something_to_search(self) -> Self:
        """
        Description:
        Odrzuca zapytanie, którego nie da się sensownie wykonać: bez frazy i bez słów, ze słowami
        krótszymi niż `MIN_LONGEST_WORD_CHARS` albo ze znakiem zerowym. Każdy z tych błędów wraca
        do modelu jako błędne argumenty.

        Example args:
            (brak)

        Example result:
            FindCodeTextQuery(exact="Brak sekwencji numeracji", words=None, path=None)

        Raises:
            ValueError: oba pola puste, same krótkie słowa albo znak zerowy w tekście
        """
        # --- nie ma czego szukać: pusta lista wyglądałaby jak „takiego tekstu nie ma w kodzie" ---
        if not self.exact and not self.words:
            raise ValueError("podaj co najmniej jedno z pól: exact, words")

        # --- same krótkie słowa: pasują do większości linii kodu ---
        if self.words and max(len(word) for word in self.words.split()) < MIN_LONGEST_WORD_CHARS:
            raise ValueError(
                f"w words co najmniej jedno słowo ma mieć {MIN_LONGEST_WORD_CHARS} znaki"
            )

        # --- znak zerowy: nie da się go przekazać programowi, który szuka ---
        if "\0" in (self.exact or "") or "\0" in (self.words or ""):
            raise ValueError("tekst do szukania zawiera znak zerowy")

        return self


class MatchedLine(BaseModel):
    """
    Description:
    Jedna linia kodu zwrócona przez `find_code_text`: plik, numer linii, czym ją znaleziono i jej
    treść. Ścieżka i numer wracają w kształcie, w jakim model poda je narzędziu cytującemu.

    Treść jest tu celowo, inaczej niż w wyszukiwaniach zgłoszeń i dokumentacji: bez niej model
    nie odróżni definicji od setek użyć tej samej nazwy, a źródłem odpowiedzi i tak jest dopiero
    fragment zacytowany jako przyczyna (`quote_code`), nie to, co model zobaczył.
    """

    model_config = ConfigDict(extra="forbid")

    path:       str       = Field(min_length=1, examples=["src/lib/Urzad/Numeracja/Generator.php"])
    line:       int       = Field(ge=1, examples=[18])
    matched_by: MatchKind = Field(examples=["exact"])
    # Bez wcięcia; linia dłuższa niż `MAX_TEXT_CHARS` jest ucięta i kończy się znakiem „…".
    text:       str       = Field(examples=["throw new BrakSekwencjiException('Brak sekwencji…"])


class FindCodeTextResult(BaseModel):
    """
    Description:
    Co dało jedno szukanie `find_code_text`: znalezione linie i liczba pasujących ponad limit.
    Licznik idzie razem z liniami, bo „trafień jest dwadzieścia" i „pokazano dwadzieścia
    z pięciuset" to różne odpowiedzi — druga mówi agentowi, że trzeba zawęzić szukanie.
    """

    model_config = ConfigDict(extra="forbid")

    lines:              list[MatchedLine] = Field(default_factory=list)
    omitted_over_limit: int               = Field(default=0, ge=0, examples=[493])
