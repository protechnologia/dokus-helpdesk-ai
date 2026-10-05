from pydantic import BaseModel, Field


class ResolutionClass(BaseModel):
    """
    Description:
    Jeden rodzaj rozstrzygnięcia, którym może skończyć się zgłoszenie. `name` trafia do
    `ParsedTicket.resolution`; `hint` jest dla promptu parsującego, który musi powiedzieć
    modelowi, co wartość znaczy — gołą listę identyfikatorów model klasyfikuje na wyczucie.
    """

    name: str = Field(examples=["bez_zmian_w_systemie"])
    hint: str = Field(examples=["w systemie nic nie zmieniono — klient dostał wskazówkę"])
