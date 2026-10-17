"""
Description:
Zmyślone próbki do testów samego helpera golden setu anonimizatora: przypadek z danymi i wiedzą,
jego wzorcowy wynik i przypadki z błędnymi zaznaczeniami. Pakiet helpera ich nie wystawia, żeby
test zestawu nie wziął ich przez pomyłkę za przypadki zestawu.
"""

from collections.abc import Mapping, Sequence

from tests._helpers.golden_anonymization.helper import _fragments_from
from tests._helpers.golden_anonymization.models.anonymization_case import AnonymizationCase
from tests._helpers.golden_anonymization.models.fragment import Fragment


def case_of(
    text:      str,                          # np. "Jan Nowak, tel. 600 123 456"
    remove:    Mapping[str, Sequence[str]],  # np. {"IMIĘ": ["Jan"]}
    keep:      Mapping[str, Sequence[str]],  # np. {"KOD_BŁĘDU": ["ORA-00942"]}
    synthetic: bool = True,                  # np. False — jak przypadek z próbki korpusu
) -> AnonymizationCase:
    """
    Description:
    Buduje przypadek z fragmentami zapisanymi po rodzaju, jak w pliku zestawu.

    Example args:
        text="Jan Nowak, tel. 600 123 456"
        remove={"IMIĘ": ["Jan"], "TELEFON": ["600 123 456"]}
        keep={}

    Example result:
        AnonymizationCase(case_id="t01", text="Jan Nowak, tel. 600 123 456", …)
    """
    case = AnonymizationCase(
        case_id    = "t01",
        phenomenon = "próbka testu helpera",
        text       = text,
        remove     = _fragments_from(remove),
        keep       = _fragments_from(keep),
        synthetic  = synthetic,
        ticket_id  = None if synthetic else "10001",
    )

    return case


# Przypadek z każdym zjawiskiem oceny: imię i nazwisko także w adresie e-mail, telefon, którego
# słowo „15” stoi też w zwykłej liczbie, i kod błędu dwa razy.
TEXT = (
    "Jan Nowak <jan.nowak@ug.pl>, tel. 81 532 10 15.\n"
    "Błąd ORA-00942 przy limicie 15 MB, ponownie ORA-00942."
)

REMOVE = {
    "IMIĘ":     ["Jan"],
    "NAZWISKO": ["Nowak"],
    "EMAIL":    ["jan.nowak@ug.pl"],
    "TELEFON":  ["81 532 10 15"],
}

KEEP = {
    "KOD_BŁĘDU": ["ORA-00942"],
    "NUMER":     ["15 MB"],
}

CASE      = case_of(TEXT, REMOVE, KEEP)
REAL_CASE = case_of(TEXT, REMOVE, KEEP, synthetic=False)

# Wzorcowy wynik: każda zaznaczona dana zamieniona na znacznik, reszta bez zmian.
CLEAN = (
    "{IMIĘ} {NAZWISKO} <{EMAIL}>, tel. {TELEFON}.\n"
    "Błąd ORA-00942 przy limicie 15 MB, ponownie ORA-00942."
)

# Telefon wycięty bez końcówki: „15” stoi w wyniku dwa razy, a poza telefonem stało raz.
PARTIAL_PHONE = (
    "{IMIĘ} {NAZWISKO} <{EMAIL}>, tel. {TELEFON} 15.\n"
    "Błąd ORA-00942 przy limicie 15 MB, ponownie ORA-00942."
)

# Adres e-mail zostawiony w całości, a imię i nazwisko przed nim wycięte.
EMAIL_LEFT = (
    "{IMIĘ} {NAZWISKO} <jan.nowak@ug.pl>, tel. {TELEFON}.\n"
    "Błąd ORA-00942 przy limicie 15 MB, ponownie ORA-00942."
)

# Imię zostawione przed nazwiskiem, adres e-mail wycięty.
NAME_LEFT = (
    "Jan {NAZWISKO} <{EMAIL}>, tel. {TELEFON}.\n"
    "Błąd ORA-00942 przy limicie 15 MB, ponownie ORA-00942."
)

# Drugie wystąpienie kodu błędu zamienione na znacznik.
CODE_LOST = (
    "{IMIĘ} {NAZWISKO} <{EMAIL}>, tel. {TELEFON}.\n"
    "Błąd ORA-00942 przy limicie 15 MB, ponownie {NUMER}."
)

# Przypadki z błędem zaznaczeń i fragment komunikatu, który `annotation_problems()` ma o nim
# podać.
BROKEN = {
    "fragment, którego nie ma w tekście": (
        case_of("Jan Nowak", {"IMIĘ": ["Anna"]}, {}),
        "IMIĘ „Anna”: nie stoi w tekście",
    ),
    "imię tylko w adresie e-mail": (
        case_of("pisze jan.nowak@ug.pl", {"IMIĘ": ["Jan"], "EMAIL": ["jan.nowak@ug.pl"]}, {}),
        "IMIĘ „Jan”: stoi tylko wewnątrz innego fragmentu",
    ),
    "dwie dane zachodzą na siebie częściowo": (
        case_of("Jan Maria Nowak", {"IMIĘ": ["Jan Maria"], "NAZWISKO": ["Maria Nowak"]}, {}),
        "IMIĘ „Jan Maria”: zachodzi na NAZWISKO „Maria Nowak”",
    ),
    "wiedza zachodzi na daną": (
        case_of(
            "Key (nip)=(5213012076)",
            {"NIP": ["5213012076"]},
            {"KOMUNIKAT": ["nip 5213012076"]},
        ),
        "KOMUNIKAT „nip 5213012076”: zachodzi na daną z listy remove",
    ),
    "wiedzy nie ma w tekście": (
        case_of("Jan Nowak", {"IMIĘ": ["Jan"]}, {"KOD_BŁĘDU": ["ORA-00942"]}),
        "KOD_BŁĘDU „ORA-00942”: nie stoi w tekście",
    ),
    "rodzaj spoza listy": (
        case_of("login jnowak", {"LOGIN": ["jnowak"]}, {}),
        "LOGIN „jnowak”: rodzaj spoza listy",
    ),
    "fragment bez słów": (
        case_of("Jan Nowak", {"IMIĘ": ["Jan"]}, {"SŁOWO": ["—"]}),
        "SŁOWO „—”: fragment bez słów",
    ),
    "ten sam fragment w obu listach": (
        case_of("Pani Mróz", {"NAZWISKO": ["Mróz"]}, {"SŁOWO": ["MRÓZ"]}),
        "SŁOWO „MRÓZ”: powtarza NAZWISKO „Mróz”",
    ),
}


def kinds(
    fragments: Sequence[Fragment],  # np. (Fragment(kind="IMIĘ", text="Jan", number=1),)
) -> list[str]:
    """
    Description:
    Rodzaje fragmentów w kolejności, do porównań w asercjach.

    Example args:
        fragments=(Fragment(kind="IMIĘ", text="Jan", number=1),)

    Example result:
        ["IMIĘ"]
    """
    return [fragment.kind for fragment in fragments]


async def leave_the_phone_end(
    text: str,  # np. TEXT
) -> str:
    """
    Description:
    Anonimizator próbny do testu pomiaru: na każdy tekst oddaje wynik z końcówką telefonu.

    Example args:
        text=TEXT

    Example result:
        PARTIAL_PHONE
    """
    return PARTIAL_PHONE
