from pydantic import BaseModel, ConfigDict


class WordAnalysis(BaseModel):
    """
    Description:
    Co słownik morfologiczny wie o jednym słowie: formy podstawowe (lematy), czy słowo w ogóle zna
    i czy któraś z jego interpretacji to imię albo nazwisko. Z tego reguła odmian
    (`core_service/finder_word_forms.py`) rozstrzyga, czy dwa słowa to ta sama osoba.
    """

    model_config = ConfigDict(frozen=True)

    lemmas:      frozenset[str]  # np. frozenset({"ewa"}) — małymi literami, bez dopisków słownika
    known:       bool            # np. True — słowo stoi w słowniku
    proper_name: bool            # np. True — któraś interpretacja to imię albo nazwisko
