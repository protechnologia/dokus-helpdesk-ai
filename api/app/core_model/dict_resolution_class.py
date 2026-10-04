from pydantic import BaseModel, Field


class ResolutionClass(BaseModel):
    """
    Description:
    One kind of outcome a ticket can end with. `name` is what lands in `ParsedTicket.resolution`;
    `hint` exists for the parsing prompt, which has to tell the model what the value means —
    a bare list of identifiers gets classified by guesswork.
    """

    name: str = Field(examples=["bez_zmian_w_systemie"])
    hint: str = Field(examples=["w systemie nic nie zmieniono — klient dostał wskazówkę"])
