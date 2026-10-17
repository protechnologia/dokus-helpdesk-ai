import dataclasses


@dataclasses.dataclass(frozen=True)
class KindCount:
    """Licznik jednego rodzaju w pomiarze: ile fragmentów tego rodzaju poszło źle, a ile było."""

    found: int  # fragmenty, które wyciekły albo zostały zniszczone, np. 3
    total: int  # wszystkie fragmenty tego rodzaju w zestawie, np. 41
