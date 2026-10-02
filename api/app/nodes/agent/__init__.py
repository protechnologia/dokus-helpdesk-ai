"""
Description:
Węzeł `agent`: jedna tura modelu — prompt grafu, dotychczasowe wiadomości i definicje narzędzi
z listy dozwolonych idą do `LLMClient`, odpowiedź (tekst albo wywołania narzędzi) wraca do
`messages`, a `iterations` rośnie o jeden. Na tej odpowiedzi graf decyduje: dalej pętla czy
odpowiedź; po przekroczeniu limitu iteracji — odpowiedź.

Status: katalog. Atrapa w p. 4, właściwy węzeł w p. 7 (CLAUDE.md -> „Plan i TODO").
"""
