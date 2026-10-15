import dataclasses

from tests._helpers.scenarios.code.models.code_fragment import CodeFragment


@dataclasses.dataclass(frozen=True)
class CodeQuote:
    """Jedno cytowanie kodu z rozmowy: fragment, rola i to, czy model te linie wcześniej czytał."""

    fragment: CodeFragment  # np. CodeFragment(path="…/RejestrSzablonow.php", 11, 25)
    role:     str           # np. "cause"; także "excluded"
    read:     bool          # wszystkie linie fragmentu oddał odczyt w jednej z wcześniejszych tur
