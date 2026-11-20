from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field


class MailTemplates(BaseModel):
    """
    Description:
    Słownik szablonów kanału „Automat mailowy”: skróty fragmentów, które stoją w wielu różnych
    wątkach tego kanału — stopek, zastrzeżeń poufności, klauzul RODO. Normalizer maili usuwa
    linie leżące w takim fragmencie także przy pierwszym wystąpieniu (p. 32).

    Plik `slownik.json` buduje `scripts/build_mail_dictionary.py` z wątków korpusu i leży obok
    `nazwy.json` w katalogu słownika maili. Fragment to ciąg `run_words` słów zapisany jako
    skrót (`core_util/repetition.run_digest()`), więc słownik nie trzyma czytelnego tekstu,
    także danych osobowych ze stopek. `run_words` jest tu, a nie w kodzie, bo skrót znaczy coś
    tylko przy tej długości, z którą go policzono.
    """

    model_config = ConfigDict(extra="forbid")

    built_on:    Date      = Field(examples=["2026-11-20"])
    # Katalog korpusu, z którego powstał słownik, w brzmieniu z polecenia budowy.
    source:      str       = Field(examples=["data/unsafe/corpus"])
    threads:     int       = Field(ge=0, examples=[139])
    run_words:   int       = Field(ge=1, examples=[12])
    min_threads: int       = Field(ge=1, examples=[10])
    digests:     list[str] = Field(examples=[["34b9d95d9a98ed46", "5be28f491fc44ae7"]])
