import re
from pathlib import Path

# Notatki redakcyjne dla nas — nie mają prawa dotrzeć do modelu. Każdy dokument promptu zaczyna się
# taką notatką (reżim zmiany, uzasadnienia z pomiarów), pisaną dla recenzenta, nie dla modelu.
_HTML_COMMENT = re.compile(r"<!--.*?-->\s*", re.DOTALL)


def read_document(
    path: Path,  # np. Path("/code/app/agent_graphs/gate_close/prompt_system.md")
) -> str:
    """
    Description:
    Czyta jeden dokument markdown i wycina z niego nasze komentarze redakcyjne. Nie wie nic
    o zgłoszeniach ani promptach — czyta plik i usuwa komentarze HTML — dlatego leży w `core_util/`,
    a nie przy którymkolwiek z wołających.

    Wspólna celowo: reguła „notatka redakcyjna nie dociera do modelu" dotyczy tak samo promptu
    parsującego, promptów grafów i opisów narzędzi, a druga kopia tego wyrażenia byłaby drugim
    miejscem, w którym da się o niej zapomnieć.

    Czyta plik przy każdym wywołaniu, bez pamiętania: odczyt największego promptu z wycięciem
    komentarzy trwa 0,15 ms (zmierzone 2026-10-12), a dokument bywa poprawiany w trakcie pracy
    usługi — opis projektu w paczce kodu, w dev także prompt.

    Example args:
        path=Path("/code/app/agent_graphs/gate_close/prompt_system.md")

    Example result:
        "Jesteś bramką jakości helpdesku. Oceniasz, czy zgłoszenie można zamknąć…"

    Raises:
        FileNotFoundError: brak dokumentu — błąd pakowania (musi być w obrazie, nie tylko
            w kopii roboczej dewelopera)
    """
    return _HTML_COMMENT.sub("", path.read_text(encoding="utf-8")).lstrip()
