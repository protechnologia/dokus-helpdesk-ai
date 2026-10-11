from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class QuestionsAnswer(BaseModel):
    """
    Description:
    Argumenty `respond_suggest_questions`: lista pytań do klienta albo jej brak, i uwagi dla
    wdrożeniowca. To kształt odpowiedzi MODELU; wynikiem grafu jest `Proposal` albo
    `ProposalNotes`, na które zamienia ją `to_output()` z graph.py.

    Do czego:
    Bywa, że pytań już nie trzeba: fakty ze zgłoszenia — z opisu albo z odpowiedzi klienta
    w wątku — zostawiają jedną przyczynę albo nic, o co dałoby się zapytać klienta. Model oddaje
    wtedy `text: null` i pisze w uwagach, które fakty to rozstrzygają, zamiast układać słabsze
    pytania. `Proposal` tego nie wyrazi, bo wymaga treści: jest wspólny dla trzech wariantów,
    a w wariancie z rozwiązaniem propozycja bez treści nie może pochodzić od modelu.

    `text` jest wymagane, choć może być `null`: model ma o pytaniach zdecydować, a nie pominąć
    pole. Pusty napis znaczy to samo co `null`. Brak pytań wymaga uwag — bez nich wdrożeniowiec
    dostałby pustą odpowiedź bez słowa wyjaśnienia.
    """

    model_config = ConfigDict(extra="forbid")

    text:           str | None = Field(examples=["1. Od kiedy nie przychodzą przesyłki? …"])
    internal_notes: str        = Field(examples=["1: odcina zacięcie kolejki (zgł. 41002)"])

    @field_validator("text")
    @classmethod
    def blank_text_means_no_questions(
        cls,
        text: str | None,  # np. "1. Od kiedy…" albo "  " albo None
    ) -> str | None:
        """
        Description:
        Zamienia pusty napis na brak pytań. Model, który nie ma pytań, bywa że odda pusty tekst
        zamiast `null`; odsyłanie tego do poprawki kosztowałoby turę, a znaczenie jest to samo.

        Example args:
            text="  "

        Example result:
            None
        """
        if text is None or not text.strip():
            return None

        return text

    @model_validator(mode="after")
    def check_no_questions_are_explained(self) -> "QuestionsAnswer":
        """
        Description:
        Odrzuca brak pytań bez uwag dla wdrożeniowca.

        Example args:
            (brak)

        Example result:
            QuestionsAnswer(text=None, internal_notes="Pytań już nie trzeba: klient potwierdził…")

        Raises:
            ValueError: `text` bez pytań i puste `internal_notes`
        """
        if self.text is None and not self.internal_notes.strip():
            raise ValueError(
                "brak pytań (text: null) wymaga uwag (internal_notes): napisz, które fakty ze "
                "zgłoszenia rozstrzygają sprawę"
            )

        return self
