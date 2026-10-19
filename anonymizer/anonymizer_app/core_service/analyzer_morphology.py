"""
Description:
Analiza morfologiczna słowa słownikiem Morfeusz2 (SGJP): formy podstawowe, to, czy słownik słowo
zna, i czy któraś interpretacja to imię albo nazwisko. Reguła odmian osób
(`finder_word_forms.py`) rozstrzyga nią, czy dwa słowa to ta sama osoba: „Ewie” i „Ewa” mają
jeden lemat, a „Alarm” i „Ala” — różne, choć zaczynają się tak samo.

| słowo        | lematy                         | w słowniku | imię albo nazwisko |
|--------------|--------------------------------|------------|--------------------|
| „Ewie”       | ewa                            | tak        | tak                |
| „Lista”      | lista                          | tak        | nie                |
| „Gądkiem”    | gądek                          | tak        | tak                |
| „Sobczakową” | —                              | nie        | nie                |

O czym pamiętać przy zmianach:

- Słownik ładuje się raz na proces (0,44 s, zmierzone 2026-10-19), przy pierwszym użyciu; fabryka
  silnika woła `load_dictionary()` przy starcie, żeby pierwsze zgłoszenie nie czekało i żeby
  zepsuta instalacja zatrzymała usługę od razu.
- Analiza słowa trwa około 0,25 ms, a wątek ma setki słów sprawdzanych dla każdego wskazanego
  słowa, więc wyniki są pamiętane na słowo.
- Słownik siedzi w bibliotece z koła `morfeusz2` (licencja BSD), bez osobnych plików.
"""

from functools import lru_cache

import morfeusz2

from anonymizer_app.core_model.word_analysis import WordAnalysis

# Kwalifikatory interpretacji, które znaczą osobę: imię albo nazwisko. Nazwa geograficzna osobą
# nie jest, choć bywa tym samym słowem („Lis” to też miejscowość).
PERSON_QUALIFIERS = frozenset({"imię", "nazwisko"})

# Znacznik słowa spoza słownika w odpowiedzi Morfeusza.
UNKNOWN_TAG = "ign"

# Ile analiz słów pamiętać. Wątek ma kilkaset różnych słów; zapas obejmuje cały proces usługi.
CACHED_WORDS = 100_000


@lru_cache(maxsize=1)
def load_dictionary() -> morfeusz2.Morfeusz:
    """
    Description:
    Słownik morfologiczny wspólny dla procesu, ładowany raz.

    Example args:
        (brak)

    Example result:
        morfeusz2.Morfeusz ze słownikiem SGJP
    """
    return morfeusz2.Morfeusz()


@lru_cache(maxsize=CACHED_WORDS)
def analyse_word(
    word: str,  # np. "Ewie"
) -> WordAnalysis:
    """
    Description:
    Lematy słowa (małymi literami, bez dopisków słownika po dwukropku), to, czy słownik je zna,
    i czy któraś interpretacja to imię albo nazwisko. Słowo spoza słownika ma pusty zbiór
    lematów.

    Example args:
        word="Ewie"

    Example result:
        WordAnalysis(lemmas=frozenset({"ewa"}), known=True, proper_name=True)
    """
    lemmas: set[str] = set()
    proper_name = False

    # Każda interpretacja to (początek, koniec, (forma, lemat, znacznik, kwalifikatory, etykiety)).
    for _, _, (_, lemma, tag, qualifiers, _) in load_dictionary().analyse(word):
        if tag == UNKNOWN_TAG:
            return WordAnalysis(lemmas=frozenset(), known=False, proper_name=False)

        lemmas.add(lemma.split(":")[0].lower())
        proper_name = proper_name or bool(PERSON_QUALIFIERS & set(qualifiers))

    analysis = WordAnalysis(lemmas=frozenset(lemmas), known=True, proper_name=proper_name)

    return analysis
