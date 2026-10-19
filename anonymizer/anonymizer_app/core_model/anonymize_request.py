from pydantic import BaseModel, Field


class AnonymizeRequest(BaseModel):
    """
    Description:
    Wejście `POST /anonymize`: jeden tekst — cały wątek zgłoszenia albo wiadomość, tak jak trafia
    do węzła `anonymize` w `api`.
    """

    text: str = Field(min_length=1, examples=["Jan Nowak zgłasza, że przesyłki nie przychodzą."])
