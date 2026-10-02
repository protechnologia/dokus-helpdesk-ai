from app.graph import merge_sources
from app.tools import SourceRef


def make_ref(
    item_id: str = "90001",  # np. "90002"
) -> SourceRef:
    """
    Description:
    Buduje źródło z `find_tickets`, różniące się tylko id.

    Example args:
        item_id="90001"

    Example result:
        SourceRef(source="find_tickets", item_id="90001", title="Brak przesyłek", score=0.9)
    """
    return SourceRef(source="find_tickets", item_id=item_id, title="Brak przesyłek", score=0.9)


def test_merge_sources_skips_what_is_already_there() -> None:
    """Drugie trafienie tego samego zgłoszenia → na liście raz, z pierwszego trafienia; nowe
    źródła dochodzą na koniec, w kolejności."""
    current = [make_ref("90001")]
    new     = [make_ref("90001"), make_ref("90002")]

    assert [ref.item_id for ref in merge_sources(current, new)] == ["90001", "90002"]


def test_merge_sources_keeps_the_same_id_from_another_tool() -> None:
    """To samo id z innego narzędzia → osobne źródło: klucz to `source:item_id`, nie samo id."""
    ticket   = make_ref("33644")
    fragment = SourceRef(source="find_docs", item_id="33644", title="Instrukcja 4.12", score=0.7)

    assert len(merge_sources([ticket], [fragment])) == 2
