from pydantic import BaseModel, Field


class RawComment(BaseModel):
    """
    Description:
    Jeden komentarz wątku źródłowego, już bez HTML-u. `kind` i `role` trafiają do promptu jako
    KONTEKST, nigdy jako rozstrzygnięcie: prompt sam mówi modelowi, żeby im nie ufał, bo w tym
    korpusie komentarz oznaczony `rozwiazanie` bywa pytaniem, a prawdziwe rozwiązanie siedzi
    czasem w komentarzu bez oznaczenia (CLAUDE.md -> „Pułapki tej bazy").
    """

    kind:       str = Field(examples=["rozwiazanie", "zwyczajny"])
    role:       str = Field(examples=["konsultant", "klient"])
    created_at: str = Field(examples=["2026-06-23 12:01:21"])
    body:       str = Field(examples=["Wygenerowano certyfikat z właściwym uprawnieniem."])
